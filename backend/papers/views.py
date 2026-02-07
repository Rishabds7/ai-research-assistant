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
from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile

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
        
        SELF-HEALING: Automatically re-triggers processing for orphaned papers 
        (papers that were created but never processed due to lost Celery tasks).
        """
        from django.utils import timezone
        from datetime import timedelta
        
        queryset = Paper.objects.all()
        session_id = self.request.headers.get('X-Session-ID')
        
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        else:
            # Fallback: If no session ID, valid behavior is debatable. 
            # For this demo, let's return nothing to encourage frontend to send the ID.
            queryset = queryset.none()
        
        # SELF-HEALING: Find orphaned papers (unprocessed, created > 2 mins ago)
        two_minutes_ago = timezone.now() - timedelta(minutes=2)
        orphaned_papers = queryset.filter(
            processed=False,
            uploaded_at__lt=two_minutes_ago
        )
        
        # Re-trigger processing for orphaned papers
        for paper in orphaned_papers:
            # Check if there's already a pending task for this paper
            existing_task = TaskStatus.objects.filter(
                result__icontains=str(paper.id),
                status__in=['pending', 'running']
            ).first()
            
            if not existing_task:
                # Re-trigger the processing task
                task = process_pdf_task.delay(str(paper.id))
                TaskStatus.objects.create(
                    task_id=task.id,
                    task_type='process_pdf',
                    status='pending'
                )
            
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
    def delete_all(self, request):
        """Delete all papers and associated data."""
        Paper.objects.all().delete()
        TaskStatus.objects.all().delete()
        return Response({'status': 'all papers and data deleted'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def ingest_arxiv(self, request):
        """
        Ingests a paper directly from ArXiv.
        Accepts: {'url': 'https://arxiv.org/abs/2303.12345'} or {'url': '2303.12345'}
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
            from django.db import transaction
            
            def trigger_task():
                task = process_pdf_task.delay(str(paper.id))
                TaskStatus.objects.create(
                    task_id=task.id,
                    task_type='process_pdf',
                    status='pending'
                )
            
            if transaction.get_connection().in_atomic_block:
                transaction.on_commit(trigger_task)
            else:
                trigger_task()

            return Response({
                'paper': PaperDetailSerializer(paper).data,
                'message': 'Ingest started'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f"ArXiv fetch failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def export_bibtex(self, request, pk=None):
        """
        Generates a BibTeX entry for the paper.
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
    def get(self, request, task_id):
        task = get_object_or_404(TaskStatus, task_id=task_id)
        serializer = TaskStatusSerializer(task)
        return Response(serializer.data)

class PingView(views.APIView):
    def get(self, request):
        return Response({"status": "online", "message": "Backend is running!"}, status=status.HTTP_200_OK)
