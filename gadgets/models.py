from django.db import models
from django.db.models import Sum

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class Gadget(models.Model):
    """Represents a gadget available for booking."""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='gadgets')
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='gadgets/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Qty: {self.quantity})"

    def available_quantity(self, start_date, end_date):
        """
        Calculate available quantity for a date range.
        Counts active (Pending + Approved) bookings that overlap with the requested dates.
        An overlap exists when:  booking_start <= end_date AND booking_end >= start_date
        """
        # We need to import Booking dynamically to avoid circular imports if Booking is in core.models
        from core.models import Booking
        overlapping_bookings = Booking.objects.filter(
            gadget=self,
            status='pending',
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return self.quantity - overlapping_bookings

    def is_available(self, start_date, end_date):
        return self.available_quantity(start_date, end_date) > 0
