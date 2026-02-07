from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "healthy"})

from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    path('', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/', include('papers.urls')),
    
    # Manual media serving for non-debug mode (Render fallback)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
