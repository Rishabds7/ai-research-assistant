"""
ROOT URL CONFIGURATION
Project: Research Assistant
File: backend/core/urls.py

The main entry point for all URL routing.
Includes admin, API, and static media serving.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.views.static import serve

def health_check(request: HttpRequest) -> JsonResponse:
    """Simple health check endpoint for container orchestration."""
    return JsonResponse({"status": "healthy"})

urlpatterns = [
    path('', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/', include('papers.urls')),
    
    # Using re_path for serving media in development/docker environments
    # This acts as a fallback when Nginx is not serving media
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
