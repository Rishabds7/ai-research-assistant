"""
URL CONFIGURATION
Project: Research Assistant
File: backend/papers/urls.py

Routes API requests (e.g., /api/papers/) to the appropriate View logic.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaperViewSet, TaskStatusView, PingView, CollectionViewSet

router = DefaultRouter()
router.register(r'papers', PaperViewSet, basename='paper')
router.register(r'collections', CollectionViewSet, basename='collection')

urlpatterns = [
    path('', include(router.urls)),
    path('ping/', PingView.as_view(), name='ping'),
    path('tasks/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
]
