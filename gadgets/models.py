from django.db import models
from django.db.models import Sum
from django.utils import timezone
from datetime import date
from django.conf import settings

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
        overlapping_bookings = Booking.objects.filter(
            gadget=self,
            status='pending',
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return self.quantity - overlapping_bookings

    def is_available(self, start_date, end_date):
        return self.available_quantity(start_date, end_date) > 0

class Booking(models.Model):
    """Represents a gadget booking/request by a student."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    gadget = models.ForeignKey(Gadget, on_delete=models.CASCADE, related_name='bookings')
    
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    
    # Approval details
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_bookings')
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        # We handle get_full_name if the user model provides it
        full_name = self.student.get_full_name() if hasattr(self.student, 'get_full_name') else self.student.email
        return f"{full_name} - {self.gadget.name} ({self.status})"

    @property
    def is_overdue(self):
        """Check if approved booking is past end date and not returned."""
        if self.status == 'approved' and self.end_date < date.today():
            return True
        return False

    def save(self, *args, **kwargs):
        if self.pk:
            # We use a try-except because in some edge cases (like bulk operations) 
            # the object might not be in the DB yet even if it has a PK.
            try:
                old_obj = Booking.objects.get(pk=self.pk)
                # If status changed to Approved, subtract from stock
                if old_obj.status != 'approved' and self.status == 'approved':
                    self.gadget.quantity -= self.quantity
                    self.gadget.save()
                # If status changed FROM Approved to something else, add back to stock
                elif old_obj.status == 'approved' and self.status != 'approved':
                    self.gadget.quantity += self.quantity
                    self.gadget.save()
            except Booking.DoesNotExist:
                # If it's a new object but somehow has a PK, check if it's already approved
                if self.status == 'approved':
                    self.gadget.quantity -= self.quantity
                    self.gadget.save()
        elif self.status == 'approved':
            # New booking created as approved (rare but for completeness)
            self.gadget.quantity -= self.quantity
            self.gadget.save()
            
        super().save(*args, **kwargs)

    def mark_returned(self):
        if self.status == 'approved':
            self.status = 'returned'
            self.returned_at = timezone.now()
            self.save()

# --- SIGNALS ---
from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=Booking)
def return_stock_on_delete(sender, instance, **kwargs):
    """Ensure stock is returned if an approved booking is deleted."""
    if instance.status == 'approved':
        instance.gadget.quantity += instance.quantity
        instance.gadget.save()
