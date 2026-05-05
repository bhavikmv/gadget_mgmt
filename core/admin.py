from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Student, Booking

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'is_staff']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'gr_number', 'phone']
    search_fields = ['user__email', 'gr_number']

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
