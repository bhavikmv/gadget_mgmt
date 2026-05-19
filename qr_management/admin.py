from django.contrib import admin
from .models import QRCode, ScanLog

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ('request', 'secure_token', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('request__id', 'secure_token')

@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ('request', 'scan_type', 'scanned_by', 'scanned_at')
    list_filter = ('scan_type', 'scanned_at')
    search_fields = ('request__id', 'scanned_by__username')
