"""
DATA SERIALIZERS
Project: Research Assistant
File: backend/papers/serializers.py

Converts Database Models into JSON format for the Frontend API.
"""
from typing import Any, Dict, List, Optional, Union
import json
from rest_framework import serializers
from .models import Paper, Methodology, SectionSummary, TaskStatus, Collection


class CollectionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for collection list views.
    
    Attributes:
        paper_count (int): Number of papers in the collection.
        paper_ids (List[UUID]): List of paper IDs for client-side duplicate checking.
    """
    paper_count = serializers.SerializerMethodField()
    paper_ids = serializers.SerializerMethodField()
    
    class Meta:
        model = Collection
        fields = ['id', 'name', 'description', 'paper_count', 'paper_ids', 'gap_analysis', 'gap_analysis_updated_at', 'created_at', 'updated_at']
    
    def get_paper_count(self, obj: Collection) -> int:
        """Returns the total number of papers in the collection."""
        return obj.papers.count()
    
    def get_paper_ids(self, obj: Collection) -> List[Any]:
        """Returns list of paper IDs for duplicate detection."""
        return list(obj.papers.values_list('id', flat=True))


class CollectionDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer with nested paper data.
    """
    papers = serializers.SerializerMethodField()
    
    class Meta:
        model = Collection
        fields = ['id', 'name', 'description', 'papers', 'gap_analysis', 'gap_analysis_updated_at', 'created_at', 'updated_at']
    
    def get_papers(self, obj: Collection) -> List[Dict[str, Any]]:
        """
        Return all papers in this collection, regardless of session.
        
        Args:
            obj: The Collection instance.
            
        Returns:
            List[Dict]: Serialized data of papers.
        """
        # Use PaperListSerializer for nested papers
        # Don't filter by session - papers in a collection should all be visible
        
        # NOTE: PaperListSerializer is defined later in this file, but available at runtime
        # We need to import it carefully or use global scope. 
        # Using global scope assuming module is fully loaded.
        try:
            # Check if PaperListSerializer is in globals
            serializer_cls = globals().get('PaperListSerializer')
            if not serializer_cls:
                # Fallback import if for some reason it's not
                from .serializers import PaperListSerializer as ImportedSerializer
                serializer_cls = ImportedSerializer
                
            papers = obj.papers.all()
            print(f"DEBUG: Collection {obj.id} ({obj.name}) has {papers.count()} papers")
            for p in papers:
                print(f"DEBUG: - Paper {p.id}: {p.title}")
            return serializer_cls(papers, many=True).data
        except Exception as e:
            print(f"DEBUG: Error serializing papers for collection {obj.id}: {e}")
            return []


class MethodologySerializer(serializers.ModelSerializer):
    """Serializer for the Methodology extraction model."""
    class Meta:
        model = Methodology
        fields = ['id', 'datasets', 'model', 'metrics', 'results', 'summary', 'created_at']


class SectionSummarySerializer(serializers.ModelSerializer):
    """Serializer for individual section summaries."""
    class Meta:
        model = SectionSummary
        fields = ['id', 'section_name', 'summary', 'order_index']


class PaperListSerializer(serializers.ModelSerializer):
    """
    Lighter serializer for list views (dashboard).
    Excludes large fields like full_text and sections to save bandwidth.
    """
    methodology = MethodologySerializer(read_only=True)
    section_summaries = SectionSummarySerializer(many=True, read_only=True)
    authors = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()
    
    class Meta:
        model = Paper
        fields = ['id', 'filename', 'file', 'uploaded_at', 'processed', 'methodology', 'section_summaries', 'metadata', 'task_ids', 'title', 'authors', 'notes', 'global_summary', 'swot_analysis', 'swot_analysis_updated_at']
    
    def get_authors(self, obj: Paper) -> str:
        """
        Format authors as clean text instead of JSON string.
        
        Args:
            obj: The Paper instance.
            
        Returns:
            str: Comma-separated authors or original string.
        """
        if not obj.authors or obj.authors == 'Unknown':
            return obj.authors
        try:
            # If it's a JSON array, convert to comma-separated string
            if isinstance(obj.authors, str) and obj.authors.startswith('['):
                authors_list = json.loads(obj.authors)
                if isinstance(authors_list, list):
                    return ', '.join(authors_list)
        except (json.JSONDecodeError, ValueError):
            pass
        return obj.authors
    
    def get_metadata(self, obj: Paper) -> Dict[str, Any]:
        """
        Ensure metadata always has the expected structure with arrays.
        
        Args:
            obj: The Paper instance.
            
        Returns:
            Dict: Normalized metadata with 'datasets' and 'licenses' as lists.
        """
        metadata = obj.metadata if obj.metadata else {}
        
        # Ensure datasets and licenses are always arrays
        result = {
            'datasets': metadata.get('datasets', []) if isinstance(metadata.get('datasets'), list) else [],
            'licenses': metadata.get('licenses', []) if isinstance(metadata.get('licenses'), list) else []
        }
        
        # Include any other metadata fields
        for key, value in metadata.items():
            if key not in ['datasets', 'licenses']:
                result[key] = value
        
        return result


class PaperDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single-paper views.
    Includes full text and all sections.
    """
    methodology = MethodologySerializer(read_only=True)
    section_summaries = SectionSummarySerializer(many=True, read_only=True)
    authors = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()
    
    class Meta:
        model = Paper
        fields = ['id', 'filename', 'file', 'uploaded_at', 'processed', 'full_text', 'sections', 'methodology', 'section_summaries', 'metadata', 'task_ids', 'title', 'authors', 'notes', 'global_summary', 'swot_analysis', 'swot_analysis_updated_at']
        extra_kwargs = {
            'filename': {'read_only': True}
        }
    
    def get_authors(self, obj: Paper) -> str:
        """Format authors as clean text instead of JSON."""
        if not obj.authors or obj.authors == 'Unknown':
            return obj.authors
        try:
            # If it's a JSON array, convert to comma-separated string
            if isinstance(obj.authors, str) and obj.authors.startswith('['):
                authors_list = json.loads(obj.authors)
                if isinstance(authors_list, list):
                    return ', '.join(authors_list)
        except (json.JSONDecodeError, ValueError):
            pass
        return obj.authors
    
    def get_metadata(self, obj: Paper) -> Dict[str, Any]:
        """Ensure metadata always has the expected structure with arrays."""
        metadata = obj.metadata if obj.metadata else {}
        
        # Ensure datasets and licenses are always arrays
        result = {
            'datasets': metadata.get('datasets', []) if isinstance(metadata.get('datasets'), list) else [],
            'licenses': metadata.get('licenses', []) if isinstance(metadata.get('licenses'), list) else []
        }
        
        # Include any other metadata fields
        for key, value in metadata.items():
            if key not in ['datasets', 'licenses']:
                result[key] = value
        
        return result


class TaskStatusSerializer(serializers.ModelSerializer):
    """Serializer for Celery Task Status updates."""
    class Meta:
        model = TaskStatus
        fields = ['task_id', 'task_type', 'status', 'result', 'error', 'created_at']

