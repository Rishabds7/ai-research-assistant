from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .models import Paper, Methodology, GapAnalysis, TaskStatus
from .serializers import (
    PaperListSerializer, PaperDetailSerializer, 
    MethodologySerializer, GapAnalysisSerializer, TaskStatusSerializer
)
from .tasks import (
    process_pdf_task, extract_methodology_task, 
    extract_all_sections_task, analyze_gaps_task,
    extract_metadata_task
)
from services.llm_service import LLMService

class PaperViewSet(viewsets.ModelViewSet):
    queryset = Paper.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaperListSerializer
        return PaperDetailSerializer
    
    def create(self, request, *args, **kwargs):
        # Override create to trigger async processing
        if 'file' not in request.FILES:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
        uploaded_file = request.FILES['file']
        
        # 1. Filename check
        if Paper.objects.filter(filename=uploaded_file.name).exists():
            return Response({'error': 'A paper with this filename already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paper = serializer.save(filename=uploaded_file.name)
        
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
        GapAnalysis.objects.all().delete()
        return Response({'status': 'all papers and data deleted'}, status=status.HTTP_200_OK)

class GapAnalysisView(views.APIView):
    def post(self, request):
        paper_ids = request.data.get('paper_ids', [])
        if not paper_ids:
             return Response({'error': 'No paper_ids provided'}, status=status.HTTP_400_BAD_REQUEST)
             
        task = analyze_gaps_task.delay(paper_ids)
        TaskStatus.objects.create(
            task_id=task.id,
            task_type='gap_analysis',
            status='pending'
        )
        return Response({'task_id': task.id})

class ComparisonView(views.APIView):
    def post(self, request):
        paper_ids = request.data.get('paper_ids', [])
        methodologies = Methodology.objects.filter(paper_id__in=paper_ids)
        
        meth_data = []
        for m in methodologies:
            meth_data.append({
                "paper": m.paper.filename,
                "dataset": m.datasets,
                "model": m.model,
                "metrics": m.metrics,
                "results": m.results,
                "contribution": m.summary # backward compat
            })
            
        llm = LLMService()
        # This is fast enough to run synchronously usually, but could be tasked
        # For now, synchronous
        try:
            table_md = llm.generate_comparison_table(meth_data)
            return Response({'markdown': table_md})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TaskStatusView(views.APIView):
    def get(self, request, task_id):
        task = get_object_or_404(TaskStatus, task_id=task_id)
        serializer = TaskStatusSerializer(task)
        return Response(serializer.data)

class PingView(views.APIView):
    def get(self, request):
        return Response({"status": "online", "message": "Backend is running!"}, status=status.HTTP_200_OK)
