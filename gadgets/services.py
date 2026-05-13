"""
gadgets/services.py
-------------------
Business logic layer for availability prediction, queue processing, and stock management.
All database mutations use atomic transactions to prevent race conditions.
"""

from datetime import date
from django.db import transaction
from django.db.models import Sum


def calculate_next_available_date(gadget):
    """
    Calculate the earliest date when at least 1 unit of `gadget` will be available.

    Strategy:
      1. If stock is already available → return today.
      2. Look at all currently-issued request-items for this gadget, sorted by
         expected_return_date ascending.
      3. Walk through the return schedule, accumulating returning quantity.
         The first date where cumulative returns make available_quantity > 0 is returned.
      4. If no return dates are scheduled → return None.
    """
    from .models import RequestItem

    if gadget.available_quantity > 0:
        return date.today()

    # Gather issued items ordered by return date
    issued_items = (
        RequestItem.objects
        .filter(request__status='issued', gadget=gadget)
        .select_related('request')
        .order_by('request__expected_return_date')
    )

    if not issued_items.exists():
        return None

    # Simulate cumulative returns
    simulated_issued = gadget.issued_quantity
    simulated_reserved = gadget.reserved_quantity

    for item in issued_items:
        simulated_issued -= item.quantity
        available = gadget.total_quantity - simulated_reserved - simulated_issued
        if available > 0:
            return item.request.expected_return_date

    return None


def calculate_queue_estimated_date(gadget, requested_quantity, target_queue_position):
    """
    Estimate when a student at `target_queue_position` (1-based) can be fulfilled.

    Strategy:
      - Build a timeline of returning stock (date → qty).
      - Simulate queue fulfilment: first process students ahead in queue, then our student.
      - Return the estimated date when `requested_quantity` becomes available for this position.
    """
    from .models import RequestItem, WaitingQueue

    # Build return schedule: list of (date, qty) sorted ascending
    issued_items = (
        RequestItem.objects
        .filter(request__status='issued', gadget=gadget)
        .select_related('request')
        .order_by('request__expected_return_date')
    )

    # Start from current stock state
    available = gadget.available_quantity
    issued = gadget.issued_quantity
    reserved = gadget.reserved_quantity

    # Queue entries ordered by position (only those ahead and including target)
    queue_entries = list(
        WaitingQueue.objects
        .filter(gadget=gadget, notified=False)
        .order_by('queue_position')[:target_queue_position]
    )

    # Return schedule as list of (date, qty_returning)
    schedule = []
    for item in issued_items:
        ret_date = item.request.expected_return_date
        if ret_date:
            schedule.append((ret_date, item.quantity))

    if not schedule:
        if available >= requested_quantity:
            return date.today()
        return None

    # Simulate queue processing against the schedule
    pool = available
    schedule_idx = 0
    current_date = date.today()

    for q_entry in queue_entries:
        needed = q_entry.quantity
        # Keep pulling from return schedule until we have enough
        while pool < needed and schedule_idx < len(schedule):
            ret_date, ret_qty = schedule[schedule_idx]
            pool += ret_qty
            current_date = ret_date
            schedule_idx += 1

        if pool >= needed:
            pool -= needed  # This queue entry gets fulfilled
        else:
            # Cannot be fulfilled based on known returns
            return None

    return current_date if current_date >= date.today() else date.today()


@transaction.atomic
def process_queue_after_return(gadget):
    """
    After a gadget return, check the waiting queue and:
      - Notify the first queue entry if enough stock is now available.
      - Optionally auto-create a Request for them (set to 'pending' for admin review).

    Returns the list of WaitingQueue entries that were notified.
    """
    from .models import WaitingQueue

    notified = []
    # Re-fetch gadget with lock
    gadget_locked = gadget.__class__.objects.select_for_update().get(pk=gadget.pk)

    entries = WaitingQueue.objects.filter(
        gadget=gadget_locked, notified=False
    ).order_by('queue_position')

    for entry in entries:
        if gadget_locked.available_quantity >= entry.quantity:
            entry.notified = True
            entry.save(update_fields=['notified'])
            notified.append(entry)
            break  # Notify one at a time; admin will action it

    return notified


def get_gadget_stats(gadget):
    """Return a dict of full stock stats for a gadget, including queue info."""
    from .models import WaitingQueue

    next_date = calculate_next_available_date(gadget)
    waitlist_count = WaitingQueue.objects.filter(gadget=gadget, notified=False).count()

    return {
        'gadget': gadget,
        'total': gadget.total_quantity,
        'available': gadget.available_quantity,
        'reserved': gadget.reserved_quantity,
        'issued': gadget.issued_quantity,
        'next_available_date': next_date,
        'waitlist_count': waitlist_count,
        'status': gadget.stock_status(),
    }
