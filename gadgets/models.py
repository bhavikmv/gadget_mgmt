from django.db import models
from django.utils import timezone
from datetime import date
from django.conf import settings
from django.db import transaction

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

class Gadget(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='gadgets')
    description = models.TextField(blank=True)
    
    total_quantity = models.PositiveIntegerField(default=1)
    reserved_quantity = models.PositiveIntegerField(default=0)
    issued_quantity = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='gadgets/', blank=True, null=True)
    expected_return_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Total: {self.total_quantity})"

    @property
    def available_quantity(self):
        return max(0, self.total_quantity - self.reserved_quantity - self.issued_quantity)

    def stock_status(self):
        available = self.available_quantity
        if available > 5:
            return 'Available'
        elif 1 <= available <= 5:
            return 'Almost Full'
        elif available == 0:
            if self.expected_return_date and self.expected_return_date >= date.today():
                return 'Available Soon'
            return 'Out of Stock'
        return 'Unknown'

    def next_available_date(self):
        if self.available_quantity > 0:
            return date.today()
        return self.expected_return_date

class Request(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('ready', 'Ready for Issue'),
        ('issued', 'Issued'),
        ('rejected', 'Rejected'),
        ('returned', 'Returned'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    expected_issue_date = models.DateField(null=True, blank=True)
    expected_return_date = models.DateField()
    
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request #{self.id} - {self.student.email} ({self.get_status_display()})"

class RequestItem(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='items')
    gadget = models.ForeignKey(Gadget, on_delete=models.CASCADE, related_name='request_items')
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.gadget.name}"

class WaitingQueue(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='waiting_queues')
    gadget = models.ForeignKey(Gadget, on_delete=models.CASCADE, related_name='waiting_queues')
    quantity = models.PositiveIntegerField(default=1)
    
    queue_position = models.PositiveIntegerField(default=0)
    notified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['queue_position']
        unique_together = ('student', 'gadget')

    def __str__(self):
        return f"Queue #{self.queue_position} - {self.student.email} for {self.gadget.name}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.queue_position:
            last_pos = WaitingQueue.objects.filter(gadget=self.gadget).order_by('-queue_position').first()
            self.queue_position = (last_pos.queue_position + 1) if last_pos else 1
        super().save(*args, **kwargs)
