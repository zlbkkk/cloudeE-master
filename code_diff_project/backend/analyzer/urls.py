from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnalysisReportViewSet, 
    AnalysisTaskViewSet, 
    ProjectRelationViewSet,
    GitOrganizationViewSet,
    DiscoveredProjectViewSet,
    DashboardViewSet
)

router = DefaultRouter()
router.register(r'reports', AnalysisReportViewSet)
router.register(r'tasks', AnalysisTaskViewSet)
router.register(r'project-relations', ProjectRelationViewSet)
router.register(r'git-organizations', GitOrganizationViewSet)
router.register(r'discovered-projects', DiscoveredProjectViewSet)
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
