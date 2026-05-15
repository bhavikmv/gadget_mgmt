from django.contrib import admin
from .models import Category, Gadget, Request, RequestItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Gadget)
class GadgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'total_quantity', 'reserved_quantity', 'issued_quantity', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']

class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 1

@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'status', 'expected_issue_date', 'expected_return_date', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['student__email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [RequestItemInline]


