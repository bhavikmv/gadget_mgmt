from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth routes handled by accounts app
    path('', include('accounts.urls')),
    
    # Gadgets and core student/admin routes handled by gadgets app
    path('', include('gadgets.urls')),
]

# Serve media files on Render (workaround for small projects)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
