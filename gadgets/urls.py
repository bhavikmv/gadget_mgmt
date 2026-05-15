from django.urls import path
from . import views

urlpatterns = [
    # ── API ──────────────────────────────────────────────────────────────────
    path('api/gadget/<int:gadget_id>/', views.gadget_detail_api, name='gadget_api'),

    # ── Student views ─────────────────────────────────────────────────────────
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('request/', views.request_gadget_view, name='request_gadget'),
    path('gadgets/', views.gadgets_view, name='gadgets'),

    # ── Admin Dashboard ───────────────────────────────────────────────────────
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),

    # ── Admin Requests ────────────────────────────────────────────────────────
    path('admin-panel/requests/', views.admin_requests_view, name='admin_requests'),
    path('admin-panel/requests/<int:pk>/', views.admin_request_detail, name='admin_request_detail'),
    path('admin-panel/requests/<int:pk>/approve/', views.admin_approve_request, name='admin_approve'),
    path('admin-panel/requests/<int:pk>/ready/', views.admin_mark_ready, name='admin_mark_ready'),
    path('admin-panel/requests/<int:pk>/issue/', views.admin_issue_request, name='admin_issue'),
    path('admin-panel/requests/<int:pk>/reject/', views.admin_reject_request, name='admin_reject'),
    path('admin-panel/requests/<int:pk>/return/', views.admin_mark_returned, name='admin_return'),


    # ── Admin Gadgets ─────────────────────────────────────────────────────────
    path('admin-panel/gadgets/', views.admin_gadgets_view, name='admin_gadgets'),
    path('admin-panel/gadgets/add/', views.admin_gadget_add, name='admin_gadget_add'),
    path('admin-panel/gadgets/<int:pk>/edit/', views.admin_gadget_edit, name='admin_gadget_edit'),
    path('admin-panel/gadgets/<int:pk>/delete/', views.admin_gadget_delete, name='admin_gadget_delete'),

    # ── Admin Categories ──────────────────────────────────────────────────────
    path('admin-panel/categories/', views.admin_categories_view, name='admin_categories'),
    path('admin-panel/categories/add/', views.admin_category_add, name='admin_category_add'),
    path('admin-panel/categories/<int:pk>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin-panel/categories/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),
]
