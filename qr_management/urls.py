from django.urls import path
from . import views

app_name = 'qr_management'

urlpatterns = [
    path('scanner/', views.qr_scanner_view, name='scanner'),
    path('api/process-scan/', views.process_qr_scan, name='process_scan'),
]
