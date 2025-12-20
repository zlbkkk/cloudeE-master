from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnalysisReportViewSet, AnalysisTaskViewSet, ProjectRelationViewSet

router = DefaultRouter()
router.register(r'reports', AnalysisReportViewSet)
router.register(r'tasks', AnalysisTaskViewSet)
router.register(r'project-relations', ProjectRelationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
