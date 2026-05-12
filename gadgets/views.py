from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from datetime import date, timedelta
from django.utils import timezone
from django.core.cache import cache

from .models import Category, Gadget, Booking
from .forms import CategoryForm, GadgetForm, BookingFormSet
from accounts.models import Student
from notifications.tasks import send_notification_email_task

def is_admin(user):
    return user.is_authenticated and user.is_staff

try:
    from ratelimit.decorators import ratelimit
except ImportError:
    # Fallback decorator if ratelimit is not installed
    def ratelimit(key=None, rate=None, block=False):
        def decorator(func):
            return func
        return decorator

# ─── STUDENT VIEWS ────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    bookings = Booking.objects.filter(student=request.user).select_related('gadget')
    context = {
        'bookings': bookings,
        'pending': bookings.filter(status='pending'),
        'approved': bookings.filter(status='approved'),
        'rejected': bookings.filter(status='rejected'),
        'returned': bookings.filter(status='returned'),
    }
    return render(request, 'student/dashboard.html', context)

@ratelimit(key='user', rate='5/m', block=True)
@login_required
def request_gadget_view(request):
    today = date.today()
    if request.method == 'POST':
        formset = BookingFormSet(request.POST)
        if formset.is_valid():
            bookings_to_create = []
            for form in formset:
                if form.cleaned_data:
                    gadget = form.cleaned_data['gadget']
                    days = int(form.cleaned_data['days'])
                    quantity = form.cleaned_data['quantity']
                    start_date = today
                    end_date = start_date + timedelta(days=days - 1)

                    bookings_to_create.append(Booking(
                        student=request.user,
                        gadget=gadget,
                        start_date=start_date,
                        end_date=end_date,
                        days=days,
                        quantity=quantity,
                        status='pending',
                    ))
            
            if bookings_to_create:
                created_bookings = Booking.objects.bulk_create(bookings_to_create)
                created_bookings = Booking.objects.filter(
                    student=request.user,
                    requested_at__gte=timezone.now() - timedelta(seconds=5)
                )

                if created_bookings:
                    for booking in created_bookings:
                        if booking.id:
                            send_notification_email_task.delay(booking.id, 'placed')

                    messages.success(
                                        request,
                                        f'{len(bookings_to_create)} request(s) submitted successfully!'
                                    )
                
                messages.success(request, f'{len(bookings_to_create)} request(s) submitted successfully!')
                return redirect('dashboard')
            else:
                messages.warning(request, "Please select at least one gadget.")
        else:
            messages.error(request, "There were errors in your request.")
    else:
        formset = BookingFormSet()

    gadgets = Gadget.objects.filter(is_active=True)
    return render(request, 'student/request.html', {
        'formset': formset,
        'gadgets': gadgets,
        'today': today,
    })

@login_required
def gadgets_view(request):
    query = request.GET.get('q', '')
    if query:
        gadgets = Gadget.objects.filter(is_active=True).select_related('category')
        gadgets = gadgets.filter(Q(name__icontains=query) | Q(category__name__icontains=query))
    else:
        gadgets = cache.get_or_set('active_gadgets_list', 
                                   Gadget.objects.filter(is_active=True).select_related('category'), 
                                   300)
    return render(request, 'student/gadgets.html', {'gadgets': gadgets, 'query': query})

@login_required
def gadget_detail_api(request, gadget_id):
    try:
        gadget = Gadget.objects.get(id=gadget_id, is_active=True)
        days = int(request.GET.get('days', 1))
        start_date = date.today()
        end_date = start_date + timedelta(days=days - 1)
        available = gadget.available_quantity(start_date, end_date)
        return JsonResponse({
            'id': gadget.id,
            'name': gadget.name,
            'category': gadget.category.name if gadget.category else 'Uncategorized',
            'description': gadget.description,
            'quantity': gadget.quantity,
            'available': available,
            'start_date': start_date.strftime('%d %b %Y'),
            'end_date': end_date.strftime('%d %b %Y'),
        })
    except Gadget.DoesNotExist:
        return JsonResponse({'error': 'Gadget not found'}, status=404)

# ─── ADMIN VIEWS ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard_view(request):
    pending = Booking.objects.filter(status='pending').count()
    approved = Booking.objects.filter(status='approved').count()
    total_gadgets = Gadget.objects.filter(is_active=True).count()
    total_students = Student.objects.count()
    
    overdue = Booking.objects.filter(
        status='approved',
        end_date__lt=date.today()
    ).count()

    recent_requests = Booking.objects.select_related('student', 'gadget').order_by('-requested_at')[:10]
    gadgets = Gadget.objects.filter(is_active=True)

    context = {
        'pending': pending,
        'approved': approved,
        'total_gadgets': total_gadgets,
        'total_students': total_students,
        'overdue': overdue,
        'recent_requests': recent_requests,
        'gadgets': gadgets,
    }
    return render(request, 'admin_panel/dashboard.html', context)

@user_passes_test(is_admin, login_url='/login/')
def admin_requests_view(request):
    status_filter = request.GET.get('status', '')
    bookings = Booking.objects.select_related('student', 'gadget').all()
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    return render(request, 'admin_panel/requests.html', {
        'bookings': bookings,
        'status_filter': status_filter,
    })

@user_passes_test(is_admin, login_url='/login/')
def admin_request_detail(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    return render(request, 'admin_panel/request_detail.html', {'booking': booking})

@user_passes_test(is_admin, login_url='/login/')
def admin_approve_request(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        available = booking.gadget.available_quantity(booking.start_date, booking.end_date)
        if booking.status == 'approved':
            messages.info(request, 'This request is already approved.')
            return redirect('admin_requests')

        if available < booking.quantity:
            messages.error(request, 'Cannot approve: not enough units available for the selected dates.')
            return redirect('admin_requests')
        
        booking.status = 'approved'
        booking.approved_by = request.user
        booking.admin_notes = request.POST.get('admin_notes', '')
        booking.save()
        messages.success(request, f'Booking #{booking.id} approved and stock updated!')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_reject_request(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        booking.status = 'rejected'
        booking.admin_notes = request.POST.get('admin_notes', '')
        booking.save()
        messages.success(request, f'Booking #{booking.id} rejected.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_mark_returned(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        booking.mark_returned()
        messages.success(request, f'Booking #{booking.id} marked as returned.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_gadgets_view(request):
    gadgets = Gadget.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/gadgets.html', {'gadgets': gadgets})

@user_passes_test(is_admin, login_url='/login/')
def admin_categories_view(request):
    categories = Category.objects.annotate(gadget_count=Count('gadgets')).order_by('name')
    return render(request, 'admin_panel/categories.html', {'categories': categories})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully!')
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Add'})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/category_form.html', {'form': form, 'action': 'Edit', 'category': category})

@user_passes_test(is_admin, login_url='/login/')
def admin_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, f'Category "{category.name}" deleted.')
    return redirect('admin_categories')

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_add(request):
    if request.method == 'POST':
        form = GadgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Gadget added successfully!')
            return redirect('admin_gadgets')
    else:
        form = GadgetForm()
    return render(request, 'admin_panel/gadget_form.html', {'form': form, 'action': 'Add'})

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_edit(request, pk):
    gadget = get_object_or_404(Gadget, pk=pk)
    if request.method == 'POST':
        form = GadgetForm(request.POST, instance=gadget)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{gadget.name}" updated successfully!')
            return redirect('admin_gadgets')
    else:
        form = GadgetForm(instance=gadget)
    return render(request, 'admin_panel/gadget_form.html', {'form': form, 'action': 'Edit', 'gadget': gadget})

@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_delete(request, pk):
    gadget = get_object_or_404(Gadget, pk=pk)
    if request.method == 'POST':
        gadget.delete()
        messages.success(request, f'"{gadget.name}" deleted successfully.')
    return redirect('admin_gadgets')
