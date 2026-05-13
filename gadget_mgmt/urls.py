from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth routes handled by accounts app
    path('', include('accounts.urls')),

    # Gadgets and core student/admin routes handled by gadgets app
    path('', include('gadgets.urls')),
]
