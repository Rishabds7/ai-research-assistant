import logging
import uuid
from celery import shared_task
from django.conf import settings

from .models import Paper, Methodology, SectionSummary, GapAnalysis, TaskStatus
from services.pdf_processor import PDFProcessor
from services.llm_service import LLMService
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

def sanitize_text(text):
    """Remove NUL characters which are not supported by PostgreSQL."""
    if isinstance(text, str):
        return text.replace('\x00', '')
    if isinstance(text, dict):
        return {k: sanitize_text(v) for k, v in text.items()}
    if isinstance(text, list):
        return [sanitize_text(i) for i in text]
    return text

def update_task_status(task_id, status, result=None, error=None):
    """Helper to update TaskStatus model."""
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
    1. Extract text/sections from PDF.
    2. Store in Paper model.
    3. Generate embeddings.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        
        # 1. Process PDF
        processor = PDFProcessor()
        # The file is stored in media/papers/filename.pdf
        # Assuming paper.file.path gives absolute path
        data = processor.process_pdf(paper.file.path, str(paper.id))
        
        # 2. Update Paper model (Sanitize text for PostgreSQL)
        paper.full_text = sanitize_text(data['full_text'])
        paper.sections = sanitize_text(data['sections'])
        paper.processed = True
        paper.save()
        
        # 3. Generate Embeddings
        embed_service = EmbeddingService()
        embed_service.store_embeddings(paper, paper.sections)
        
        update_task_status(task_id, 'completed', result={"paper_id": str(paper.id)})
        return {"status": "success", "paper_id": str(paper.id)}
        
    except Exception as e:
        logger.error(f"Error processing PDF {paper_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def extract_methodology_task(self, paper_id):
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        
        # Use full methodology section if available, else RAG
        sections = paper.sections
        # Normalize keys
        sections_lower = {k.lower(): v for k,v in sections.items()}
        
        context = sections_lower.get('methodology') or sections_lower.get('method')
        
        if not context:
            # Fallback to RAG via embeddings if context missing
            # But for now, let's just use first 5 chunks similar to specific query?
            # Or simplified: use extracted text from Methodology-like sections
            pass
            
        if not context:
             # Just take first 10000 chars of full text if no sections detected?
             # Or try to search embedding service?
             # Let's use Embedding Service search
             embed_svc = EmbeddingService()
             results = embed_svc.search("methodology method experimental setup", k=5)
             # Filter for this paper
             paper_results = [r for r in results if r['paper_id'] == str(paper.id)]
             if paper_results:
                 context = "\n".join([r['text'] for r in paper_results])
             else:
                 context = paper.full_text[:10000] # Fallback
                 
        llm = LLMService()
        data = llm.extract_methodology(context)
        
        # Save to DB
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
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        sections = paper.sections # already dict
        
        if not sections:
            # Maybe try to re-detect if empty?
            pass
            
        llm = LLMService()
        summaries = llm.smart_summarize_paper(paper.full_text, sections)
        
        # Save to DB
        # Re-verify paper exists to avoid IntegrityError if deleted mid-task
        if not Paper.objects.filter(id=paper_id).exists():
            logger.warning(f"Paper {paper_id} deleted during section extraction.")
            return summaries

        # Delete old summaries
        SectionSummary.objects.filter(paper=paper).delete()
        
        new_summaries = []
        for i, (name, text) in enumerate(summaries.items()):
            new_summaries.append(
                SectionSummary(
                    paper=paper, 
                    section_name=name, 
                    summary=sanitize_text(text),
                    order_index=i
                )
            )
        SectionSummary.objects.bulk_create(new_summaries)
        
        # Clear the task_id from Paper model
        if 'summarize' in paper.task_ids:
            del paper.task_ids['summarize']
            paper.save(update_fields=['task_ids'])
        
        update_task_status(task_id, 'completed', result=summaries)
        return summaries

    except Exception as e:
        try:
            paper = Paper.objects.get(id=paper_id)
            if 'summarize' in paper.task_ids:
                del paper.task_ids['summarize']
                paper.save(update_fields=['task_ids'])
        except: pass
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def extract_metadata_task(self, paper_id, field):
    """
    field: 'datasets' or 'licenses'
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        llm = LLMService()
        
        # 1. Smarter Context Selection
        # Instead of just the first 12k chars, let's look for relevant sections
        context = ""
        sections = paper.sections or {}
        
        if field == 'datasets':
            # Priority: A large contiguous block of the beginning is often better than fragmented parts
            # But we must respect the LLM provider's context limits
            is_ollama = getattr(llm, 'provider', '').lower() == 'ollama'
            limit = 20000 if is_ollama else 60000
            
            # 1. Start with first portion of the paper
            context = "### PAPER START & EARLY FIGURES\n" + paper.full_text[:limit]
            
            # 2. If it's not Ollama, we can afford to add more sections
            if not is_ollama:
                target_keywords = ["experiment", "evaluation", "benchmark", "results", "analysis"]
                sections_to_append = []
                for name, content in sections.items():
                    if any(k in name.lower() for k in target_keywords):
                        if content[:200] not in context:
                            sections_to_append.append(f"### {name.upper()}\n{content}")
                
                if sections_to_append:
                    context += "\n\n" + "\n\n".join(sections_to_append)
                    context = context[:80000] # Final cap for high-end models
            
            result = llm.extract_datasets(context)
            
        elif field == 'licenses':
            # Licenses are often in Introduction, Footnotes, or Acknowledgments
            target_keywords = ["introduction", "acknowledgment", "reference", "appendix"]
            found_sections = []
            for name, content in sections.items():
                if any(k in name.lower() for k in target_keywords):
                    found_sections.append(content)
            
            # Also check the very beginning of the paper (first page usually has footnotes)
            if found_sections:
                context = paper.full_text[:5000] + "\n\n" + "\n\n".join(found_sections)[:10000]
            else:
                context = paper.full_text[:15000]
                
            result = llm.extract_licenses(context)
        else:
            raise ValueError(f"Unknown metadata field: {field}")
            
        # Update metadata JSONField (ensuring Django detects the change)
        meta = paper.metadata.copy() if paper.metadata else {}
        meta[field] = result
        paper.metadata = meta
        
        # Clear the task_id
        if field in paper.task_ids:
            del paper.task_ids[field]
            
        paper.save(update_fields=['metadata', 'task_ids'])
        
        update_task_status(task_id, 'completed', result={field: result})
        return {field: result}
        
    except Exception as e:
        try:
            paper = Paper.objects.get(id=paper_id)
            if field in paper.task_ids:
                del paper.task_ids[field]
                paper.save(update_fields=['task_ids'])
        except: pass
        logger.error(f"Error extracting {field} for {paper_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True)
def analyze_gaps_task(self, paper_ids):
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        # Get methodologies
        methodologies = Methodology.objects.filter(paper_id__in=paper_ids)
        meth_data = []
        for m in methodologies:
            meth_data.append({
                "paper": m.paper.filename,
                "model": m.model,
                "metrics": m.metrics,
                "summary": m.summary
            })
            
        llm = LLMService()
        gaps_result = llm.identify_gaps(meth_data)
        
        # Save GapAnalysis object
        defaults = {
            'methodological_gaps': gaps_result.get('methodological_gaps', []),
            'dataset_limitations': gaps_result.get('dataset_limitations', []),
            'evaluation_gaps': gaps_result.get('evaluation_gaps', []),
            'novel_directions': gaps_result.get('novel_directions', []),
        }
        
        # Create new analysis
        gap_obj = GapAnalysis.objects.create(**defaults)
        gap_obj.papers.set(paper_ids)
        
        update_task_status(task_id, 'completed', result={"gap_analysis_id": str(gap_obj.id), "data": gaps_result})
        return gaps_result

    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))
        raise
