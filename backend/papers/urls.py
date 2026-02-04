from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaperViewSet, GapAnalysisView, ComparisonView, TaskStatusView, PingView

router = DefaultRouter()
router.register(r'papers', PaperViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('ping/', PingView.as_view(), name='ping'),
    path('analysis/gaps/', GapAnalysisView.as_view(), name='gap-analysis'),
    path('analysis/comparison/', ComparisonView.as_view(), name='comparison'),
    path('tasks/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
]
