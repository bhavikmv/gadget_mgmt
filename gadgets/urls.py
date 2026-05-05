from django.urls import path
from . import views

urlpatterns = [
    # API endpoints
    path('api/gadget/<int:gadget_id>/', views.gadget_detail_api, name='gadget_api'),
    
    # Student views
    path('gadgets/', views.gadgets_view, name='gadgets'),
    
    # Admin gadget views
    path('admin-panel/gadgets/', views.admin_gadgets_view, name='admin_gadgets'),
    path('admin-panel/gadgets/add/', views.admin_gadget_add, name='admin_gadget_add'),
    path('admin-panel/gadgets/<int:pk>/edit/', views.admin_gadget_edit, name='admin_gadget_edit'),
    path('admin-panel/gadgets/<int:pk>/delete/', views.admin_gadget_delete, name='admin_gadget_delete'),
    
    # Admin category views
    path('admin-panel/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-panel/categories/add/', views.admin_category_add, name='admin_category_add'),
    path('admin-panel/categories/<int:pk>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin-panel/categories/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),
]
