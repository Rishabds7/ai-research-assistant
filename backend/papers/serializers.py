"""
DATA SERIALIZERS
Project: Research Assistant
File: backend/papers/serializers.py

Converts Database Models into JSON format for the Frontend API.
"""
from rest_framework import serializers
from .models import Paper, Methodology, SectionSummary, TaskStatus

class MethodologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Methodology
        fields = ['id', 'datasets', 'model', 'metrics', 'results', 'summary', 'created_at']

class SectionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SectionSummary
        fields = ['id', 'section_name', 'summary', 'order_index']

class PaperListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views."""
    methodology = MethodologySerializer(read_only=True)
    section_summaries = SectionSummarySerializer(many=True, read_only=True)
    
    class Meta:
        model = Paper
        fields = ['id', 'filename', 'file', 'uploaded_at', 'processed', 'methodology', 'section_summaries', 'metadata', 'task_ids', 'title', 'authors', 'notes', 'global_summary']

class PaperDetailSerializer(serializers.ModelSerializer):
    methodology = MethodologySerializer(read_only=True)
    section_summaries = SectionSummarySerializer(many=True, read_only=True)
    
    class Meta:
        model = Paper
        fields = ['id', 'filename', 'file', 'uploaded_at', 'processed', 'full_text', 'sections', 'methodology', 'section_summaries', 'metadata', 'task_ids', 'title', 'authors', 'notes', 'global_summary']
        extra_kwargs = {
            'filename': {'read_only': True}
        }

class TaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskStatus
        fields = ['task_id', 'task_type', 'status', 'result', 'error', 'created_at']

