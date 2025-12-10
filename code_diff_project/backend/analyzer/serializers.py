from rest_framework import serializers
from .models import AnalysisReport, AnalysisTask

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
