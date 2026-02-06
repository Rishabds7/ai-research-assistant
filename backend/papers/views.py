"""
API VIEWS
Project: Research Assistant
File: backend/papers/views.py

This file handles the logic for various API endpoints.
It uses Django Rest Framework (DRF) to handle:
1. Paper uploads and triggering background processing.
2. Individual analysis triggers (Extract Methodology, Summarize Sections).
3. Polling for background task status.
4. Bulk deletion of data.
"""
from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .models import Paper, Methodology, TaskStatus
from .serializers import (
    PaperListSerializer, PaperDetailSerializer, 
    MethodologySerializer, TaskStatusSerializer
)
from .tasks import (
    process_pdf_task, extract_methodology_task, 
    extract_all_sections_task,
    extract_metadata_task
)
from services.llm_service import LLMService

class PaperViewSet(viewsets.ModelViewSet):
    """
    The main API for Paper management.
    Includes Standard CRUD (Create, Read, Update, Delete) + Custom AI Actions.
    """
    def get_queryset(self):
        """
        Filters papers based on the 'X-Session-ID' header.
        This provides basic privacy/isolation for public demo users without full auth.
        """
        queryset = Paper.objects.all()
        session_id = self.request.headers.get('X-Session-ID')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        else:
            # Fallback: If no session ID, valid behavior is debatable. 
            # For this demo, let's return nothing to encourage frontend to send the ID.
            queryset = queryset.none()
            
        return queryset.order_by('-uploaded_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return PaperListSerializer
        return PaperDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Handles PDF upload.
        Saves the file to disk and starts the initial background task (text extraction).
        """
        # Override create to trigger async processing
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
        uploaded_file = request.FILES['file']
        session_id = request.headers.get('X-Session-ID')
        
        # 1. Filename check (scoped to session)
        if session_id and Paper.objects.filter(filename=uploaded_file.name, session_id=session_id).exists():
             return Response({'error': 'You have already uploaded this paper.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Save with session_id
        paper = serializer.save(filename=uploaded_file.name, session_id=session_id)
        
        # Trigger processing task
        task = process_pdf_task.delay(str(paper.id))

        
        # Create initial TaskStatus
        TaskStatus.objects.create(
            task_id=task.id,
            task_type='process_pdf',
            status='pending'
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response({
            'paper': serializer.data,
            'task_id': task.id
        }, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    def extract_methodology(self, request, pk=None):
        """
        Triggered when a user clicks 'Methodology' in the UI.
        Runs an AI task to extract structured technical details.
        """
        paper = self.get_object()
        if not paper.processed:
            return Response({'error': 'Paper not processed yet'}, status=status.HTTP_400_BAD_REQUEST)
            
        task = extract_methodology_task.delay(str(paper.id))
        TaskStatus.objects.create(
            task_id=task.id,
            task_type='extract_methodology',
            status='pending'
        )
        return Response({'task_id': task.id})

    @action(detail=True, methods=['post'])
    def extract_all_sections(self, request, pk=None):
        """
        Triggered when 'Summarize' is clicked.
        Generates individual section summaries and a global summary.
        """
        paper = self.get_object()
        if not paper.processed:
             return Response({'error': 'Paper not processed yet'}, status=status.HTTP_400_BAD_REQUEST)
             
        task = extract_all_sections_task.delay(str(paper.id))
        
        # Persist task_id for frontend recovery
        paper.task_ids['summarize'] = task.id
        paper.save(update_fields=['task_ids'])

        TaskStatus.objects.create(
            task_id=task.id,
            task_type='extract_sections',
            status='pending'
        )
        return Response({'task_id': task.id})

    @action(detail=True, methods=['post'])
    def extract_metadata(self, request, pk=None):
        field = request.data.get('field')
        if field not in ['datasets', 'licenses']:
            return Response({'error': 'Invalid field'}, status=status.HTTP_400_BAD_REQUEST)
            
        paper = self.get_object()
        if not paper.processed:
            return Response({'error': 'Paper not processed yet'}, status=status.HTTP_400_BAD_REQUEST)
            
        task = extract_metadata_task.delay(str(paper.id), field)
        
        # Persist task_id for frontend recovery
        paper.task_ids[field] = task.id
        paper.save(update_fields=['task_ids'])

        TaskStatus.objects.create(
            task_id=task.id,
            task_type=f'extract_{field}',
            status='pending'
        )
        return Response({'task_id': task.id})

    @action(detail=False, methods=['post'])
    def delete_all(self, request):
        """Delete all papers and associated data."""
        Paper.objects.all().delete()
        TaskStatus.objects.all().delete()
        return Response({'status': 'all papers and data deleted'}, status=status.HTTP_200_OK)


class TaskStatusView(views.APIView):
    """
    Dedicated endpoint for the frontend to poll status of long-running tasks.
    Example: GET /api/tasks/uuid-of-task/
    """
    def get(self, request, task_id):
        task = get_object_or_404(TaskStatus, task_id=task_id)
        serializer = TaskStatusSerializer(task)
        return Response(serializer.data)

class PingView(views.APIView):
    def get(self, request):
        return Response({"status": "online", "message": "Backend is running!"}, status=status.HTTP_200_OK)
