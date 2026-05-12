from django.contrib import admin
from .models import Category, Gadget, Booking

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Gadget)
class GadgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'quantity', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['student', 'gadget', 'start_date', 'end_date', 'status', 'approved_by', 'requested_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['student__email', 'gadget__name']
    readonly_fields = ['requested_at', 'updated_at', 'approved_by']
    
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Booking.objects.get(pk=obj.pk)
            # Check if status was changed to approved
            if old_obj.status != 'approved' and obj.status == 'approved':
                obj.approved_by = request.user
            # Check if status was changed to returned
            if old_obj.status != 'returned' and obj.status == 'returned':
                from django.utils import timezone
                obj.returned_at = timezone.now()
        super().save_model(request, obj, form, change)
