from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import send_mail
from django.utils import timezone
from datetime import date, timedelta

from .models import Student, Booking
from gadgets.models import Gadget, Category
from .forms import BookingForm, BookingFormSet
from notifications.tasks import send_notification_email_task


def is_admin(user):
    return user.is_authenticated and user.is_staff


# ─── STUDENT VIEWS ────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    bookings = Booking.objects.filter(student=request.user).select_related('gadget')
    # Using list() to evaluate query once and filter in memory if small, 
    # but for dashboard, separate queries are fine if they are indexed.
    context = {
        'bookings': bookings,
        'pending': bookings.filter(status='pending'),
        'approved': bookings.filter(status='approved'),
        'rejected': bookings.filter(status='rejected'),
        'returned': bookings.filter(status='returned'),
    }
    return render(request, 'student/dashboard.html', context)


try:
    from ratelimit.decorators import ratelimit
except ImportError:
    # Fallback decorator if ratelimit is not installed
    def ratelimit(key=None, rate=None, block=False):
        def decorator(func):
            return func
        return decorator

@ratelimit(key='user', rate='5/m', block=True)
@login_required
def request_gadget_view(request):
    """
    Highly optimized view for handling gadget requests.
    Uses bulk_create to minimize database hits.
    """
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
                # Use bulk_create for high performance (one SQL query instead of N)
                Booking.objects.bulk_create(bookings_to_create)
                
                # bulk_create doesn't trigger signals, so we manually trigger the email task
                # for each newly created booking.
                created_bookings = Booking.objects.filter(
                    student=request.user, 
                    requested_at__gte=timezone.now() - timedelta(seconds=5)
                )
                for booking in created_bookings:
                    send_notification_email_task.delay(booking.id, 'placed')
                
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


# ─── ADMIN VIEWS ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard_view(request):
    pending = Booking.objects.filter(status='pending').count()
    approved = Booking.objects.filter(status='approved').count()
    total_gadgets = Gadget.objects.filter(is_active=True).count()
    total_students = Student.objects.count()
    
    # Overdue bookings
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
        # Re-validate availability at time of approval
        available = booking.gadget.available_quantity(booking.start_date, booking.end_date)
        
        # If it's already approved, don't do anything
        if booking.status == 'approved':
            messages.info(request, 'This request is already approved.')
            return redirect('admin_requests')

        if available < booking.quantity:
            messages.error(request, 'Cannot approve: not enough units available for the selected dates.')
            return redirect('admin_requests')
        
        # Update status and approval details
        booking.status = 'approved'
        booking.approved_by = request.user
        booking.admin_notes = request.POST.get('admin_notes', '')
        
        # Model save() handles the gadget stock subtraction
        booking.save()
        messages.success(request, f'Booking #{booking.id} approved and stock updated!')
    return redirect('admin_requests')


@user_passes_test(is_admin, login_url='/login/')
def admin_reject_request(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        # Model save() will handle adding back to stock if it was previously approved
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


from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@gmail.com',
        password='admin123'
    )

