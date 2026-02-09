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
import re
import requests
import json
from typing import Any, Dict, List, Optional, Union
from rest_framework import viewsets, status, views
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from .models import Paper, Methodology, TaskStatus, Collection
from .serializers import (
    PaperListSerializer, PaperDetailSerializer, 
    MethodologySerializer, TaskStatusSerializer,
    CollectionDetailSerializer, CollectionListSerializer
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
    
    def get_queryset(self) -> QuerySet:
        """
        Filters papers based on the 'X-Session-ID' header.
        This provides basic privacy/isolation for public demo users without full auth.
        
        SELF-HEALING: Automatically re-triggers processing for orphaned papers 
        (papers that were created but never processed due to lost Celery tasks).
        
        Returns:
            QuerySet: Filtered list of Papers.
        """
        queryset = Paper.objects.all()
        session_id = self.request.headers.get('X-Session-ID')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        else:
            # Fallback: If no session ID, valid behavior is debatable. 
            # For this demo, let's return nothing to encourage frontend to send the ID.
            queryset = queryset.none()
        
        # SELF-HEALING: Find orphaned papers (unprocessed, created > 1 min ago)
        one_minute_ago = timezone.now() - timedelta(minutes=1)
        orphaned_papers = queryset.filter(
            processed=False,
            uploaded_at__lt=one_minute_ago
        )
        
        # Re-trigger processing for orphaned papers
        for paper in orphaned_papers:
            # Check if we have an active process_pdf task for this paper
            active_task_id = paper.task_ids.get('process_pdf')
            should_retrigger = True
            
            if active_task_id:
                existing_task = TaskStatus.objects.filter(task_id=active_task_id).first()
                # If task is already pending or running, don't double-trigger
                if existing_task and existing_task.status in ['pending', 'running']:
                    should_retrigger = False
            
            if should_retrigger:
                # Re-trigger the processing task
                task = process_pdf_task.delay(str(paper.id))
                
                # Update task_ids on paper
                paper.task_ids['process_pdf'] = task.id
                paper.save(update_fields=['task_ids'])
                
                # Create/Update TaskStatus
                TaskStatus.objects.update_or_create(
                    task_id=task.id,
                    defaults={
                        'task_type': 'process_pdf',
                        'status': 'pending'
                    }
                )
            
        return queryset.order_by('-uploaded_at')

    def get_serializer_class(self) -> Any:
        """Selects the appropriate serializer based on the action."""
        if self.action == 'list':
            return PaperListSerializer
        return PaperDetailSerializer
    
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Handles PDF upload.
        Saves the file to disk and starts the initial background task (text extraction).
        
        Args:
            request: The HTTP request containing the PDF file.
            
        Returns:
            Response: JSON with paper details and initial task ID.
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
    def extract_methodology(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Triggered when a user clicks 'Methodology' in the UI.
        Runs an AI task to extract structured technical details.
        
        Args:
            request: The HTTP request.
            pk: The UUID of the paper.
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
    def extract_all_sections(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Triggered when 'Summarize' is clicked.
        Generates individual section summaries and a global summary.
        
        Args:
            request: The HTTP request.
            pk: The UUID of the paper.
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
    def extract_metadata(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Triggers metadata extraction for specific fields (e.g. datasets, licenses).
        
        Args:
            request: HTTP Request containing 'field' in body.
            pk: UUID of the paper.
        """
        field = request.data.get('field')
        if field not in ['datasets', 'licenses']:
            return Response({'error': 'Invalid field'}, status=status.HTTP_400_BAD_REQUEST)
            
        paper = self.get_object()
        if not paper.processed:
            return Response({'error': 'Paper not processed yet'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Consistency Check: If already running or already has data, don't start new
        existing_task_id = paper.task_ids.get(field)
        if existing_task_id:
            try:
                task_status = TaskStatus.objects.get(task_id=existing_task_id)
                if task_status.status in ['pending', 'running']:
                    return Response({'task_id': existing_task_id})
                
                # If it's already completed and we have data, just return the old task ID (frontend will see the status)
                # Unless we want to force a refresh, but user wants "once for all".
                if task_status.status == 'completed' and paper.metadata.get(field):
                    return Response({'task_id': existing_task_id})
            except TaskStatus.DoesNotExist:
                pass

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
    def delete_all(self, request: Request) -> Response:
        """Delete all papers and associated data."""
        Paper.objects.all().delete()
        TaskStatus.objects.all().delete()
        return Response({'status': 'all papers and data deleted'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def ingest_arxiv(self, request: Request) -> Response:
        """
        Ingests a paper directly from ArXiv.
        Accepts: {'url': 'https://arxiv.org/abs/2303.12345'} or {'url': '2303.12345'}
        
        Args:
            request: HTTP Request with 'url' in body.
        """
        input_url = request.data.get('url', '').strip()
        session_id = request.headers.get('X-Session-ID')

        if not input_url:
            return Response({'error': 'No ArXiv URL or ID provided'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Extract ArXiv ID using Regex
        # Matches: 2303.12345, arxiv.org/abs/2303.12345, arxiv:2303.12345
        match = re.search(r'(\d{4}\.\d{4,5})', input_url)
        if not match:
            return Response({'error': 'Could not parse ArXiv ID from input'}, status=status.HTTP_400_BAD_REQUEST)
        
        arxiv_id = match.group(1)
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        filename = f"arxiv_{arxiv_id.replace('.', '_')}.pdf"

        # 2. Duplicate Check
        if session_id and Paper.objects.filter(filename=filename, session_id=session_id).exists():
             return Response({'error': 'Paper already exists in your library.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 3. Download PDF (ArXiv requires User-Agent)
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(pdf_url, stream=True, timeout=30, headers=headers)
            
            if response.status_code != 200:
                return Response({'error': f'ArXiv returned status {response.status_code}'}, status=status.HTTP_400_BAD_REQUEST)

            # 4. Save to DB
            paper = Paper(filename=filename, session_id=session_id)
            paper.file.save(filename, ContentFile(response.content), save=True)
            
            # 5. Trigger Task (Resiliently)
            
            # We generate the task ID immediately but delay execution 
            # lightly to ensure DB consistency
            task = process_pdf_task.delay(str(paper.id))
            
            # Save task ID to paper metadata for frontend persistence
            paper.task_ids['process_pdf'] = task.id
            paper.save(update_fields=['task_ids'])

            def create_status_record():
                TaskStatus.objects.get_or_create(
                    task_id=task.id,
                    defaults={
                        'task_type': 'process_pdf',
                        'status': 'pending'
                    }
                )
            
            if transaction.get_connection().in_atomic_block:
                transaction.on_commit(create_status_record)
            else:
                create_status_record()

            return Response({
                'paper': PaperDetailSerializer(paper).data,
                'task_id': task.id,
                'message': 'ArXiv ingestion started'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f"ArXiv fetch failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def export_bibtex(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Generates a BibTeX entry for the paper.
        
        Args:
            request: HTTP Request.
            pk: UUID of the paper.
            
        Returns:
            Response: JSON with 'bibtex' string.
        """
        paper = self.get_object()
        
        # Parse Authors
        authors_list = []
        try:
            if paper.authors:
                data = json.loads(paper.authors)
                if isinstance(data, list):
                    authors_list = data
                else:
                    authors_list = [paper.authors]
            else:
                authors_list = ["Unknown Author"]
        except:
            authors_list = [paper.authors] if paper.authors else ["Unknown Author"]

        authors_str = " and ".join(authors_list)
        
        # Clean title for BibTeX key
        safe_key = "".join(filter(str.isalnum, paper.title.split()[0] if paper.title else "paper"))
        year_str = paper.year if paper.year and paper.year != "Unknown" else "2024"
        cite_key = f"{safe_key.lower()}{year_str}"

        bibtex = f"""@article{{{cite_key},
  title={{{paper.title or paper.filename}}},
  author={{{authors_str}}},
  year={{{year_str}}},
  journal={{{paper.journal if paper.journal and paper.journal != "Unknown" else "ArXiv Preprint"}}},
  note={{Summarized via PaperDigest AI}}
}}"""
        
        return Response({'bibtex': bibtex})


class TaskStatusView(views.APIView):
    """
    Dedicated endpoint for the frontend to poll status of long-running tasks.
    Example: GET /api/tasks/uuid-of-task/
    """
    def get(self, request: Request, task_id: str) -> Response:
        task = get_object_or_404(TaskStatus, task_id=task_id)
        serializer = TaskStatusSerializer(task)
        return Response(serializer.data)


class CollectionViewSet(viewsets.ModelViewSet):
    """
    API for managing paper collections.
    Allows users to create, update, delete collections and manage paper membership.
    """
    def get_queryset(self) -> QuerySet:
        """Filter collections by session ID."""
        queryset = Collection.objects.all()
        session_id = self.request.headers.get('X-Session-ID')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        else:
            queryset = queryset.none()
        
        return queryset.prefetch_related('papers')
    
    def get_serializer_class(self) -> Any:
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return CollectionListSerializer
        return CollectionDetailSerializer
    
    def perform_create(self, serializer: CollectionListSerializer) -> None:
        """Automatically set session_id when creating a collection."""
        session_id = self.request.headers.get('X-Session-ID')
        serializer.save(session_id=session_id)
    
    @action(detail=True, methods=['post'])
    def add_paper(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Add a paper to this collection.
        POST /api/collections/{id}/add_paper/
        Body: { "paper_id": "uuid" }
        """
        collection = self.get_object()
        paper_id = request.data.get('paper_id')
        
        if not paper_id:
            return Response(
                {'error': 'paper_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get paper and validate it belongs to the same session
        session_id = request.headers.get('X-Session-ID')
        try:
            paper = Paper.objects.get(id=paper_id, session_id=session_id)
        except Paper.DoesNotExist:
            return Response(
                {'error': 'Paper not found or does not belong to this session'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        collection.papers.add(paper)
        
        return Response({
            'status': 'paper added',
            'collection_id': str(collection.id),
            'paper_id': str(paper.id)
        })
    
    @action(detail=True, methods=['post'])
    def remove_paper(self, request: Request, pk: Optional[str] = None) -> Response:
        """
        Remove a paper from this collection.
        POST /api/collections/{id}/remove_paper/
        Body: { "paper_id": "uuid" }
        """
        collection = self.get_object()
        paper_id = request.data.get('paper_id')
        
        if not paper_id:
            return Response(
                {'error': 'paper_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        paper = get_object_or_404(Paper, id=paper_id)
        collection.papers.remove(paper)
        
        return Response({
            'status': 'paper removed',
            'collection_id': str(collection.id),
            'paper_id': str(paper.id)
        })


class PingView(views.APIView):
    def get(self, request: Request) -> Response:
        return Response({"status": "online", "message": "Backend is running!"}, status=status.HTTP_200_OK)
