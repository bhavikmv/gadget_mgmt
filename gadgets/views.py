"""
gadgets/views.py
----------------
All student and admin views for the GadgetMS application.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from datetime import date, timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from .models import Category, Gadget, Request, RequestItem, WaitingQueue
from .forms import CategoryForm, GadgetForm, RequestForm, RequestFormSet, WaitlistForm
from .services import (
    calculate_next_available_date,
    calculate_queue_estimated_date,
    process_queue_after_return,
    get_gadget_stats,
)
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
    requests_list = (
        Request.objects
        .filter(student=request.user)
        .prefetch_related('items__gadget')
    )
    waiting_list = (
        WaitingQueue.objects
        .filter(student=request.user)
        .select_related('gadget__category')
    )

    # Annotate waiting list with estimated availability
    enriched_waiting = []
    for wq in waiting_list:
        est = calculate_queue_estimated_date(wq.gadget, wq.quantity, wq.queue_position)
        enriched_waiting.append({
            'wq': wq,
            'estimated_date': est,
        })

    gadgets = Gadget.objects.filter(is_active=True)

    context = {
        'requests': requests_list,
        'waiting_list': waiting_list,
        'enriched_waiting': enriched_waiting,
        'gadgets': gadgets,
        'pending': requests_list.filter(status='pending'),
        'waitlisted': requests_list.filter(status='waitlisted'),
        'approved': requests_list.filter(status='approved'),
        'ready': requests_list.filter(status='ready'),
        'issued': requests_list.filter(status='issued'),
        'returned': requests_list.filter(status='returned'),
    }
    return render(request, 'student/dashboard.html', context)


@ratelimit(key='user', rate='10/m', block=True)
@login_required
def request_gadget_view(request):
    today = date.today()
    gadgets = Gadget.objects.filter(is_active=True).select_related('category')

    if request.method == 'POST':
        formset = RequestFormSet(request.POST)
        if formset.is_valid():
            created_request = False
            req = None
            
            with transaction.atomic():
                for form in formset:
                    if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                        continue
                    
                    gadget = form.cleaned_data['gadget']
                    days = int(form.cleaned_data['days'])
                    quantity = form.cleaned_data['quantity']
                    join_waitlist = form.cleaned_data.get('join_waitlist', False)

                    start_date = today
                    end_date = start_date + timedelta(days=days - 1)

                    gadget_locked = Gadget.objects.select_for_update().get(pk=gadget.pk)

                    if gadget_locked.available_quantity >= quantity:
                        # Normal request flow
                        if not created_request:
                            req = Request.objects.create(
                                student=request.user,
                                status='pending',
                                expected_issue_date=start_date,
                                expected_return_date=end_date,
                            )
                            created_request = True
                        else:
                            if end_date > req.expected_return_date:
                                req.expected_return_date = end_date
                                req.save(update_fields=['expected_return_date'])

                        gadget_locked.reserved_quantity += quantity
                        gadget_locked.save(update_fields=['reserved_quantity'])
                        RequestItem.objects.create(request=req, gadget=gadget_locked, quantity=quantity)
                        messages.success(request, f'✅ Added {quantity}× {gadget_locked.name} to request.')

                    elif join_waitlist:
                        # Check duplicate
                        if WaitingQueue.objects.filter(student=request.user, gadget=gadget_locked).exists():
                            messages.warning(request, f'You are already in the waitlist for {gadget_locked.name}.')
                        else:
                            wq = WaitingQueue.objects.create(
                                student=request.user,
                                gadget=gadget_locked,
                                quantity=quantity,
                                duration_days=days,
                            )
                            # Estimate date for this queue position
                            est = calculate_queue_estimated_date(gadget_locked, quantity, wq.queue_position)
                            if est:
                                wq.estimated_availability_date = est
                                wq.save(update_fields=['estimated_availability_date'])

                            messages.info(
                                request,
                                f'📋 Added to waitlist for {gadget_locked.name}. '
                                f'Queue position: #{wq.queue_position}.'
                            )
                    else:
                        next_date = calculate_next_available_date(gadget_locked)
                        next_str = next_date.strftime('%d %b %Y') if next_date else 'Unknown'
                        messages.warning(
                            request,
                            f'⚠️ Only {gadget_locked.available_quantity} of {gadget_locked.name} available. '
                            f'Next available: {next_str}.'
                        )

            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        formset = RequestFormSet()

    return render(request, 'student/request.html', {
        'formset': formset,
        'gadgets': gadgets,
        'today': today,
    })


@login_required
def gadgets_view(request):
    query = request.GET.get('q', '').strip()
    gadgets_qs = Gadget.objects.filter(is_active=True).select_related('category')
    if query:
        gadgets_qs = gadgets_qs.filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        )

    # Enrich with computed stats
    enriched = []
    for g in gadgets_qs:
        enriched.append(get_gadget_stats(g))

    return render(request, 'student/gadgets.html', {
        'gadgets': enriched,
        'query': query,
        'total_count': gadgets_qs.count(),
    })


@login_required
def gadget_detail_api(request, gadget_id):
    try:
        g = Gadget.objects.get(id=gadget_id, is_active=True)
        next_date = calculate_next_available_date(g)
        return JsonResponse({
            'id': g.id,
            'name': g.name,
            'category': g.category.name if g.category else 'Uncategorized',
            'description': g.description,
            'total_quantity': g.total_quantity,
            'available': g.available_quantity,
            'reserved': g.reserved_quantity,
            'issued': g.issued_quantity,
            'next_available_date': next_date.strftime('%d %b %Y') if next_date else None,
            'waitlist_count': g.waitlist_count(),
            'status': g.stock_status(),
        })
    except Gadget.DoesNotExist:
        return JsonResponse({'error': 'Gadget not found'}, status=404)


# ─── ADMIN VIEWS ──────────────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_dashboard_view(request):
    pending = Request.objects.filter(status='pending').count()
    approved = Request.objects.filter(status='approved').count()
    ready = Request.objects.filter(status='ready').count()
    waitlisted_count = WaitingQueue.objects.filter(notified=False).count()
    total_gadgets = Gadget.objects.filter(is_active=True).count()
    total_students = Student.objects.count()

    overdue = Request.objects.filter(
        status='issued',
        expected_return_date__lt=date.today(),
    ).count()

    recent_requests = (
        Request.objects
        .select_related('student')
        .prefetch_related('items__gadget')
        .order_by('-created_at')[:10]
    )
    gadgets = Gadget.objects.filter(is_active=True)

    context = {
        'pending': pending,
        'approved': approved,
        'ready': ready,
        'waitlisted_count': waitlisted_count,
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
    requests_list = (
        Request.objects
        .select_related('student')
        .prefetch_related('items__gadget')
        .all()
    )
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    return render(request, 'admin_panel/requests.html', {
        'requests': requests_list,
        'status_filter': status_filter,
    })


@user_passes_test(is_admin, login_url='/login/')
def admin_request_detail(request, pk):
    req = get_object_or_404(
        Request.objects.select_related('student__student_profile').prefetch_related('items__gadget'),
        pk=pk,
    )
    return render(request, 'admin_panel/request_detail.html', {'req': req, 'today': date.today()})


# ─── STATUS CHANGE ACTIONS ────────────────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_approve_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'pending':
            req.status = 'approved'
            req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
            req.save()
            messages.success(request, f'✅ Request #{req.id} approved.')
        else:
            messages.warning(request, 'Can only approve pending requests.')
    return redirect('admin_request_detail', pk=pk)


@user_passes_test(is_admin, login_url='/login/')
def admin_mark_ready(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'approved':
            req.status = 'ready'
            req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
            req.save()
            messages.success(request, f'📦 Request #{req.id} marked Ready for Pickup.')
        else:
            messages.warning(request, 'Can only mark approved requests as ready.')
    return redirect('admin_request_detail', pk=pk)


@user_passes_test(is_admin, login_url='/login/')
def admin_issue_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status in ['approved', 'ready']:
            # Admin can override expected return date at issue time
            new_return_date = request.POST.get('expected_return_date')
            with transaction.atomic():
                req.status = 'issued'
                req.issue_date = date.today()
                req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
                if new_return_date:
                    from datetime import datetime
                    try:
                        req.expected_return_date = datetime.strptime(new_return_date, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                req.save()

                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(pk=item.gadget.pk)
                    gadget.reserved_quantity = max(0, gadget.reserved_quantity - item.quantity)
                    gadget.issued_quantity += item.quantity
                    gadget.save(update_fields=['reserved_quantity', 'issued_quantity'])

            messages.success(request, f'✅ Request #{req.id} issued. Stock updated.')
        else:
            messages.warning(request, 'Can only issue approved or ready requests.')
    return redirect('admin_request_detail', pk=pk)


@user_passes_test(is_admin, login_url='/login/')
def admin_reject_request(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status in ['pending', 'approved', 'ready']:
            with transaction.atomic():
                req.status = 'rejected'
                req.admin_notes = request.POST.get('admin_notes', req.admin_notes)
                req.save()

                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(pk=item.gadget.pk)
                    gadget.reserved_quantity = max(0, gadget.reserved_quantity - item.quantity)
                    gadget.save(update_fields=['reserved_quantity'])

            messages.success(request, f'❌ Request #{req.id} rejected. Reserved stock restored.')
        else:
            messages.warning(request, 'Cannot reject an already issued or returned request.')
    return redirect('admin_request_detail', pk=pk)


@user_passes_test(is_admin, login_url='/login/')
def admin_mark_returned(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == 'POST':
        if req.status == 'issued':
            with transaction.atomic():
                req.status = 'returned'
                req.return_date = date.today()
                req.save()

                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(pk=item.gadget.pk)
                    gadget.issued_quantity = max(0, gadget.issued_quantity - item.quantity)
                    gadget.save(update_fields=['issued_quantity'])

                    # Process queue: notify first eligible waiter
                    notified = process_queue_after_return(gadget)
                    for wq in notified:
                        messages.info(
                            request,
                            f'🔔 {wq.student.get_full_name()} (#{wq.queue_position}) '
                            f'has been notified – stock available for {wq.gadget.name}.'
                        )

            messages.success(request, f'🔄 Request #{req.id} returned. Stock restored.')
        else:
            messages.warning(request, 'Can only return issued requests.')
    return redirect('admin_request_detail', pk=pk)


# ─── ADMIN WAITING QUEUE MANAGEMENT ──────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_waiting_queue_view(request):
    """Paginated view of all waiting queue entries grouped by gadget."""
    gadget_filter = request.GET.get('gadget', '')
    queue_entries = (
        WaitingQueue.objects
        .select_related('student', 'gadget__category')
        .order_by('gadget', 'queue_position')
    )
    if gadget_filter:
        queue_entries = queue_entries.filter(gadget_id=gadget_filter)

    # Enrich with estimated dates
    enriched = []
    for wq in queue_entries:
        est = calculate_queue_estimated_date(wq.gadget, wq.quantity, wq.queue_position)
        enriched.append({'wq': wq, 'estimated_date': est})

    gadgets_with_queue = Gadget.objects.filter(waiting_queues__isnull=False).distinct()

    return render(request, 'admin_panel/waiting_queue.html', {
        'enriched': enriched,
        'gadgets_with_queue': gadgets_with_queue,
        'gadget_filter': gadget_filter,
        'total': queue_entries.count(),
    })


@user_passes_test(is_admin, login_url='/login/')
def admin_approve_queue_entry(request, pk):
    """Approve a waiting queue entry: convert it to a pending Request."""
    wq = get_object_or_404(WaitingQueue, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            gadget = Gadget.objects.select_for_update().get(pk=wq.gadget.pk)
            if gadget.available_quantity >= wq.quantity:
                days = wq.duration_days or 7
                start = date.today()
                end = start + timedelta(days=days - 1)

                gadget.reserved_quantity += wq.quantity
                gadget.save(update_fields=['reserved_quantity'])

                req = Request.objects.create(
                    student=wq.student,
                    status='approved',
                    expected_issue_date=start,
                    expected_return_date=end,
                    admin_notes='Approved from waiting queue.',
                )
                RequestItem.objects.create(request=req, gadget=gadget, quantity=wq.quantity)
                wq.delete()

                messages.success(
                    request,
                    f'✅ Queue entry approved → Request #{req.id} created for '
                    f'{wq.student.get_full_name()} ({wq.gadget.name}).'
                )
            else:
                messages.error(
                    request,
                    f'Not enough stock for {wq.gadget.name}. '
                    f'Available: {gadget.available_quantity}, needed: {wq.quantity}.'
                )
    return redirect('admin_waiting_queue')


@user_passes_test(is_admin, login_url='/login/')
def admin_reject_queue_entry(request, pk):
    """Remove a student from the waiting queue."""
    wq = get_object_or_404(WaitingQueue, pk=pk)
    if request.method == 'POST':
        name = wq.student.get_full_name()
        gadget_name = wq.gadget.name
        wq.delete()
        messages.success(request, f'🗑️ Removed {name} from waitlist for {gadget_name}.')
    return redirect('admin_waiting_queue')


# ─── ADMIN GADGET & CATEGORY VIEWS ───────────────────────────────────────────

@user_passes_test(is_admin, login_url='/login/')
def admin_gadgets_view(request):
    gadgets = Gadget.objects.all().order_by('-created_at')
    enriched = [get_gadget_stats(g) for g in gadgets]
    return render(request, 'admin_panel/gadgets.html', {'gadgets': enriched})


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
            messages.success(request, f'Category "{category.name}" updated.')
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'admin_panel/category_form.html', {
        'form': form, 'action': 'Edit', 'category': category
    })


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
        form = GadgetForm(request.POST, request.FILES)
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
        form = GadgetForm(request.POST, request.FILES, instance=gadget)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{gadget.name}" updated.')
            return redirect('admin_gadgets')
    else:
        form = GadgetForm(instance=gadget)
    return render(request, 'admin_panel/gadget_form.html', {
        'form': form, 'action': 'Edit', 'gadget': gadget
    })


@user_passes_test(is_admin, login_url='/login/')
def admin_gadget_delete(request, pk):
    gadget = get_object_or_404(Gadget, pk=pk)
    if request.method == 'POST':
        gadget.delete()
        messages.success(request, f'"{gadget.name}" deleted.')
    return redirect('admin_gadgets')
