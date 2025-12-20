from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnalysisReportViewSet, AnalysisTaskViewSet

router = DefaultRouter()
router.register(r'reports', AnalysisReportViewSet)
router.register(r'tasks', AnalysisTaskViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
