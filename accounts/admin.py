from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Student

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'is_staff']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['user', 'gr_number', 'phone']
    search_fields = ['user__email', 'gr_number']
