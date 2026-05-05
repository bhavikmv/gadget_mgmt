from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth routes handled by accounts app
    path('', include('accounts.urls')),
    
    # Gadgets routes handled by gadgets app
    path('', include('gadgets.urls')),
    
    # Student core routes
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('request/', views.request_gadget_view, name='request_gadget'),
    
    # Admin Panel core routes
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-panel/requests/', views.admin_requests_view, name='admin_requests'),
    path('admin-panel/requests/<int:pk>/', views.admin_request_detail, name='admin_request_detail'),
    path('admin-panel/requests/<int:pk>/approve/', views.admin_approve_request, name='admin_approve'),
    path('admin-panel/requests/<int:pk>/reject/', views.admin_reject_request, name='admin_reject'),
    path('admin-panel/requests/<int:pk>/return/', views.admin_mark_returned, name='admin_return'),
]
