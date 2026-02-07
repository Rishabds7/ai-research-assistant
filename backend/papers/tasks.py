"""
CELERY BACKGROUND TASKS (THE ORCHESTRATOR)
Project: Research Assistant
File: backend/papers/tasks.py

This file contains the long-running workflows that happen in the background.
We use Celery so the UI remains responsive while the AI is thinking.

AI INTERVIEW FOCUS:
1. Asynchronous Pipeline: Explain how we split 'PDF Processing' (Fast), 
   'Metadata Extraction' (Async), and 'Deep Summarization' (High Latency) into separate tasks.
2. Context Window Optimization: Study the 'extract_metadata_task'. We don't send 
   the whole 50-page paper to the LLM. We selectively 'Smart-Crop' the text 
   to include the most high-density sections (Abstract, Intro, Labs).
3. State Management: We use the 'TaskStatus' model to track the 'thinking' 
   progress of the AI, providing real-time feedback to the UI.
"""
import logging
import uuid
from celery import shared_task
from django.conf import settings

from .models import Paper, Methodology, SectionSummary, TaskStatus
from services.pdf_processor import PDFProcessor
from services.llm_service import LLMService
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

def sanitize_text(text):
    """
    CLEANING LOGIC:
    Removes NUL characters and junk that would crash the PostgreSQL JSON/Text fields.
    Ensures data integrity between the AI output and the Database.
    """
    if isinstance(text, str):
        return text.replace('\x00', '')
    if isinstance(text, dict):
        return {k: sanitize_text(v) for k, v in text.items()}
    if isinstance(text, list):
        return [sanitize_text(i) for i in text]
    return text

def update_task_status(task_id, status, result=None, error=None):
    """
    UI SYNC LOGIC:
    Updates a central 'TaskStatus' record so the frontend's 'Checking...' 
    indicator knows when to reveal the results.
    """
    try:
        ts, _ = TaskStatus.objects.get_or_create(task_id=task_id, defaults={'task_type': 'unknown'})
        ts.status = status
        if result:
            ts.result = result
        if error:
            ts.error = str(error)
        ts.save()
    except Exception as e:
        logger.error(f"Failed to update task status {task_id}: {e}")

@shared_task(bind=True)
def process_pdf_task(self, paper_id):
    """
    INITIAL INGESTION PIPELINE (Stage 1).
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        logger.info(f"Starting PDF processing for Paper {paper_id}")
        paper = Paper.objects.get(id=paper_id)
        
        # 1. Process PDF using our custom segmentation logic
        logger.info(f"Extracting text from {paper.filename}...")
        processor = PDFProcessor()
        data = processor.process_pdf(paper.file.path, str(paper.id))
        
        paper.full_text = sanitize_text(data['full_text'])
        paper.sections = sanitize_text(data['sections'])
        paper.processed = True
        paper.save(update_fields=['full_text', 'sections', 'processed'])
        logger.info("Basic text extraction successful. Paper marked as processed.")

        # 2. Metadata Extraction (Optional, don't fail the whole task if this errors)
        try:
            logger.info("Calling Gemini for metadata extraction...")
            llm = LLMService()
            # Send just the first 10k chars for metadata (fast)
            info = llm.extract_paper_info(paper.full_text[:10000])
            
            paper.title = sanitize_text(info.get('title', paper.filename))
            paper.year = sanitize_text(info.get('year', 'Unknown'))
            paper.journal = sanitize_text(info.get('journal', 'Unknown'))
            
            authors_data = info.get('authors', 'Unknown')
            if isinstance(authors_data, list):
                import json
                paper.authors = json.dumps(authors_data)
            else:
                paper.authors = sanitize_text(authors_data)
            paper.save(update_fields=['title', 'authors', 'year', 'journal'])
            logger.info(f"Metadata identified: {paper.title} ({paper.year})")
        except Exception as e:
            logger.error(f"Metadata extraction failed (non-fatal): {e}")
            if not paper.title:
                paper.title = paper.filename
                paper.save(update_fields=['title'])
            
        update_task_status(task_id, 'completed', result={"paper_id": str(paper.id)})
        
        # 3. Trigger Embeddings in a separate background task (Lower Priority / Non-Blocking)
        generate_embeddings_task.delay(str(paper.id))
        
        logger.info(f"Task {task_id} completed successfully. Embeddings triggered.")
        return {"status": "success", "paper_id": str(paper.id)}
        
    except Exception as e:
        logger.error(f"FATAL Task Error {task_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def generate_embeddings_task(self, paper_id):
    """
    NON-BLOCKING TASK: Generate semantic vectors for RAG search.
    This runs after the paper is already 'Ready' in the UI.
    """
    try:
        paper = Paper.objects.get(id=paper_id)
        logger.info(f"Generating embeddings for {paper.filename}...")
        embed_service = EmbeddingService()
        embed_service.store_embeddings(paper, paper.sections)
        logger.info("Embeddings complete.")
    except Exception as e:
        logger.error(f"Embeddings failed: {e}")

@shared_task(bind=True)
def extract_methodology_task(self, paper_id):
    """
    TECHNICAL DEEP-DIVE TASK (Stage 2).
    
    Focuses specifically on the technical stack of the paper.
    If a clear 'Methodology' section isn't found, it uses 'Smart-RAG' 
    (semantic search) to gather text related to experiments and math.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        sections_lower = {k.lower(): v for k,v in paper.sections.items()}
        
        # Context Selection: Methodology -> Methods -> RAG Fallback
        context = sections_lower.get('methodology') or sections_lower.get('method')
        
        if not context:
            embed_svc = EmbeddingService()
            results = embed_svc.search("methodology method experimental setup architecture", k=5)
            # Use chunks only from this specific paper
            paper_results = [r for r in results if r['paper_id'] == str(paper.id)]
            context = "\n".join([r['text'] for r in paper_results]) if paper_results else paper.full_text[:12000]
                 
        llm = LLMService()
        data = llm.extract_methodology(context)
        
        Methodology.objects.update_or_create(
            paper=paper,
            defaults={
                'datasets': data.get('datasets', []),
                'model': data.get('model', {}),
                'metrics': data.get('metrics', []),
                'results': data.get('results', {}),
                'summary': data.get('summary', '')
            }
        )
        update_task_status(task_id, 'completed', result=data)
        return data
    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def extract_all_sections_task(self, paper_id):
    """
    HIERARCHICAL SUMMARIZATION TASK (Stage 2).
    
    1. Summarizes individual logical sections (Abstract, Intro, etc.).
    2. Uses those summaries to generate a 'Global Summary' (Multi-stage synthesis).
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        llm = LLMService()
        
        # Intelligent summarization based on paper structure
        summaries = llm.summarize_sections(paper.sections, paper.full_text)
        
        # Persistence: save individual section summaries for the side-by-side view
        SectionSummary.objects.filter(paper=paper).delete()
        SectionSummary.objects.bulk_create([
            SectionSummary(paper=paper, section_name=name, summary=sanitize_text(text), order_index=i)
            for i, (name, text) in enumerate(summaries.items())
        ])

        # Global Synthesis: provide the TL;DR for the dashboard
        global_sum = llm.generate_global_summary(summaries)
        paper.global_summary = sanitize_text(global_sum)
        paper.save(update_fields=['global_summary', 'task_ids'])
        
        update_task_status(task_id, 'completed', result=summaries)
        return summaries
    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def extract_metadata_task(self, paper_id, field):
    """
    TARGETED EXTRACTION TASK (Ad-hoc).
    
    Triggers when the user requests specific tags like 'Datasets' or 'Licenses'.
    Study the 'Context Selection Logic' here—it's a great example of 
    handling token limits by intelligently cropping the paper text.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        llm = LLMService()
        
        # SMART CONTEXT SELECTION:
        # We only send high-density areas (Intro + targeted keywords) to the LLM.
        if field == 'datasets':
            dataset_keywords = ["dataset", "benchmark", "evaluation", "setup", "metrics"]
            target_sections = [content for name, content in paper.sections.items() 
                             if any(k in name.lower() for k in dataset_keywords)]
            context = paper.full_text[:12000] + "\n\n" + "\n\n".join(target_sections)[:30000]
            result = llm.extract_datasets(context)
        elif field == 'licenses':
            # Pass full text to service - it uses smart snippet extraction (Head 20k + Tail 40k)
            result = llm.extract_licenses(paper.full_text)
        else:
            raise ValueError(f"Unknown field: {field}")
            
        meta = paper.metadata.copy() if paper.metadata else {}
        meta[field] = result
        paper.metadata = meta
        paper.save(update_fields=['metadata', 'task_ids'])
        
        update_task_status(task_id, 'completed', result={field: result})
        return {field: result}
    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        raise
