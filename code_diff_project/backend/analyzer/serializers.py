from rest_framework import serializers
from .models import AnalysisReport, AnalysisTask, ProjectRelation, GitOrganization, DiscoveredProject

class AnalysisTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisTask
        fields = '__all__'

class AnalysisReportSerializer(serializers.ModelSerializer):
    source_branch = serializers.CharField(source='task.source_branch', read_only=True, allow_null=True)
    target_branch = serializers.CharField(source='task.target_branch', read_only=True, allow_null=True)

    class Meta:
        model = AnalysisReport
        fields = '__all__'

class ProjectRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectRelation
        fields = '__all__'

class GitOrganizationSerializer(serializers.ModelSerializer):
    default_branch = serializers.CharField(default='master', required=False)
    
    class Meta:
        model = GitOrganization
        fields = '__all__'
        extra_kwargs = {
            'access_token': {'write_only': True},  # Token 不在读取时返回
            'default_branch': {'default': 'master', 'required': False}
        }

class DiscoveredProjectSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = DiscoveredProject
        fields = '__all__'
