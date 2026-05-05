from django.contrib import admin
from .models import Category, Gadget

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Gadget)
class GadgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'quantity', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']
