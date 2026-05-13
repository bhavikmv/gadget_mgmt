from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from datetime import date, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from .models import Category, Gadget, Request, RequestItem, WaitingQueue
from .forms import CategoryForm, GadgetForm, RequestFormSet
from accounts.models import Student
from notifications.tasks import send_notification_email_task

def is_admin(user):
    return user.is_authenticated and user.is_staff

try:
    from ratelimit.decorators import ratelimit
except ImportError:
    def ratelimit(key=None, rate=None, block=False):
        def decorator(func):
            return func
        return decorator

# ─── STUDENT VIEWS ────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    requests_list = Request.objects.filter(student=request.user).prefetch_related('items__gadget')
    waiting_list = WaitingQueue.objects.filter(student=request.user).select_related('gadget')
    
    context = {
        'requests': requests_list,
        'waiting_list': waiting_list,
        'pending': requests_list.filter(status='pending'),
        'approved': requests_list.filter(status='approved'),
        'ready': requests_list.filter(status='ready'),
        'issued': requests_list.filter(status='issued'),
        'returned': requests_list.filter(status='returned'),
    }
    return render(request, 'student/dashboard.html', context)

@ratelimit(key='user', rate='5/m', block=True)
@login_required
def request_gadget_view(request):
    today = date.today()
    if request.method == 'POST':
        formset = RequestFormSet(request.POST)
        if formset.is_valid():
            success_count = 0
            waitlist_count = 0
            
            with transaction.atomic():
                for form in formset:
                    if form.cleaned_data:
                        gadget = form.cleaned_data['gadget']
                        days = int(form.cleaned_data['days'])
                        quantity = form.cleaned_data['quantity']
                        join_waitlist = form.cleaned_data.get('join_waitlist', False)
                        
                        start_date = today
                        end_date = start_date + timedelta(days=days - 1)
                        
                        # Lock the gadget row for update to prevent race conditions
                        gadget = Gadget.objects.select_for_update().get(id=gadget.id)
                        
                        if gadget.available_quantity >= quantity:
                            gadget.reserved_quantity += quantity
                            gadget.save()
                            
                            req = Request.objects.create(
                                student=request.user,
                                status='pending',
                                expected_return_date=end_date
                            )
                            RequestItem.objects.create(request=req, gadget=gadget, quantity=quantity)
                            success_count += 1
                        else:
                            if join_waitlist:
                                WaitingQueue.objects.create(
                                    student=request.user,
                                    gadget=gadget,
                                    quantity=quantity
                                )
                                waitlist_count += 1
                            else:
                                messages.warning(request, f"Not enough stock for '{gadget.name}'. Please select 'Join waitlist' to reserve it in advance.")
                
            if success_count > 0:
                messages.success(request, f'{success_count} request(s) submitted successfully! Gadgets have been reserved.')
            if waitlist_count > 0:
                messages.info(request, f'You have been added to the waitlist for {waitlist_count} gadget(s).')
                
            return redirect('dashboard')
        else:
            messages.error(request, "There were errors in your request.")
    else:
        formset = RequestFormSet()

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
        return JsonResponse({
            'id': gadget.id,
            'name': gadget.name,
            'category': gadget.category.name if gadget.category else 'Uncategorized',
            'description': gadget.description,
            'total_quantity': gadget.total_quantity,
            'available': gadget.available_quantity,
            'expected_return_date': gadget.expected_return_date.strftime('%d %b %Y') if gadget.expected_return_date else None,
            'status': gadget.stock_status(),
        })
    except Gadget.DoesNotExist:
        return JsonResponse({'error': 'Gadget not found'}, status=404)


# ─── ADMIN VIEWS ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard_view(request):
    pending = Request.objects.filter(status='pending').count()
    approved = Request.objects.filter(status='approved').count()
    ready = Request.objects.filter(status='ready').count()
    total_gadgets = Gadget.objects.filter(is_active=True).count()
    total_students = Student.objects.count()
    
    overdue = Request.objects.filter(
        status='issued',
        expected_return_date__lt=date.today()
    ).count()

    recent_requests = Request.objects.select_related('student').prefetch_related('items__gadget').order_by('-created_at')[:10]
    gadgets = Gadget.objects.filter(is_active=True)

    context = {
        'pending': pending,
        'approved': approved,
        'ready': ready,
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
    requests_list = Request.objects.select_related('student').prefetch_related('items__gadget').all()
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    return render(request, 'admin_panel/requests.html', {
        'requests': requests_list,
        'status_filter': status_filter,
    })

@user_passes_test(is_admin, login_url='/login/')
def admin_request_detail(request, pk):
    req = get_object_or_404(Request, pk=pk)
    return render(request, 'admin_panel/request_detail.html', {'request': req})


# --- STATUS CHANGE ACTIONS ---
@user_passes_test(is_admin, login_url='/login/')
def admin_approve_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'pending':
            req.status = 'approved'
            req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
            req.save()
            messages.success(request, f'Request #{req.id} approved (Waiting for Issue).')
        else:
            messages.warning(request, 'Can only approve pending requests.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_mark_ready(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'approved':
            req.status = 'ready'
            req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
            req.save()
            messages.success(request, f'Request #{req.id} marked as Ready for Pickup.')
        else:
            messages.warning(request, 'Can only mark approved requests as ready.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_issue_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status in ['approved', 'ready']:
            with transaction.atomic():
                req.status = 'issued'
                req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
                req.save()
                
                # Update quantities: reserved -> issued
                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(id=item.gadget.id)
                    gadget.reserved_quantity -= item.quantity
                    gadget.issued_quantity += item.quantity
                    gadget.save()
                    
            messages.success(request, f'Request #{req.id} issued. Stock updated.')
        else:
            messages.warning(request, 'Can only issue approved or ready requests.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_reject_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status in ['pending', 'approved', 'ready']:
            with transaction.atomic():
                req.status = 'rejected'
                req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
                req.save()
                
                # Restore reserved quantity
                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(id=item.gadget.id)
                    gadget.reserved_quantity -= item.quantity
                    gadget.save()
                    
            messages.success(request, f'Request #{req.id} rejected. Reserved stock restored.')
        else:
            messages.warning(request, 'Cannot reject an already issued or returned request.')
    return redirect('admin_requests')

@user_passes_test(is_admin, login_url='/login/')
def admin_mark_returned(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'issued':
            with transaction.atomic():
                req.status = 'returned'
                req.save()
                
                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(id=item.gadget.id)
                    gadget.issued_quantity -= item.quantity
                    gadget.save()
                    
                    # Notify waitlist if there's someone waiting
                    waitlist_entries = WaitingQueue.objects.filter(gadget=gadget, notified=False).order_by('queue_position')
                    for queue in waitlist_entries:
                        if gadget.available_quantity >= queue.quantity:
                            # Here we could send an email notification
                            queue.notified = True
                            queue.save()
                            break # Notify next person who fits
                            
            messages.success(request, f'Request #{req.id} marked as returned. Stock restored.')
        else:
            messages.warning(request, 'Can only return issued requests.')
    return redirect('admin_requests')


# ─── ADMIN GADGET & CATEGORY VIEWS ──────────────────────────────────────────────

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
