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

def get_gadget_stats(gadget):
    """Return a dict of full stock stats for a gadget."""
    next_date = calculate_next_available_date(gadget)

    return {
        'gadget': gadget,
        'total': gadget.total_quantity,
        'available': gadget.available_quantity,
        'reserved': gadget.reserved_quantity,
        'issued': gadget.issued_quantity,
        'next_available_date': next_date,
        'status': gadget.stock_status(),
    }
