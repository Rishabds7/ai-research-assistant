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
import json
from typing import Any, Dict, List, Optional, Union
from celery import shared_task
from django.conf import settings

from .models import Paper, Methodology, SectionSummary, TaskStatus
from services.pdf_processor import PDFProcessor
from services.llm_service import LLMService
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

def sanitize_text(text: Union[str, Dict, List, Any]) -> Union[str, Dict, List, Any]:
    """
    CLEANING LOGIC:
    Removes NUL characters and junk that would crash the PostgreSQL JSON/Text fields.
    Ensures data integrity between the AI output and the Database.
    
    Args:
        text: Input text, dict, or list.
        
    Returns:
        Sanitized input with NUL characters removed.
    """
    if isinstance(text, str):
        return text.replace('\x00', '')
    if isinstance(text, dict):
        return {k: sanitize_text(v) for k, v in text.items()}
    if isinstance(text, list):
        return [sanitize_text(i) for i in text]
    return text

def update_task_status(task_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    """
    UI SYNC LOGIC:
    Updates a central 'TaskStatus' record so the frontend's 'Checking...' 
    indicator knows when to reveal the results.
    
    Args:
        task_id: The Celery task UUID.
        status: The new status string (e.g., 'running', 'completed').
        result: Optional JSON result data.
        error: Optional error message.
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

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_pdf_task(self, paper_id: str) -> Dict[str, str]:
    """
    INITIAL INGESTION PIPELINE (Stage 1 - FAST PATH).
    
    Goal: Get the paper to "Processed" state AS FAST AS POSSIBLE (< 5s).
    We only do the physical text extraction here.
    AI analysis (Title, Authors, Embeddings) happens in background tasks.
    
    Args:
        paper_id: UUID of the Paper record.
        
    Returns:
        Dict: Status message.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        processor = PDFProcessor()
        
        # 1. FAST PATH: Immediate metadata extraction for UI
        # We do this FIRST so the next polling cycle sees the title/authors
        try:
            fast_meta = processor.get_metadata(paper.file.path)
            paper.title = sanitize_text(fast_meta.get("title") or paper.filename)
            if fast_meta.get("authors"):
                paper.authors = json.dumps(fast_meta["authors"])
            else:
                paper.authors = json.dumps(["Processing..."])
            paper.save(update_fields=['title', 'authors'])
        except Exception as e:
            logger.warning(f"Fast-path metadata failed for {paper_id}: {e}")
        
        # 2. PHYSICAL EXTRACTION (CPU Bound - potentially slow for large PDFs)
        try:
            text = processor.extract_text(paper.file.path)
            if not text or len(text.strip()) < 100:
                error_msg = 'Failed to extract meaningful text from PDF.'
                update_task_status(task_id, 'failed', error=error_msg)
                return {'error': error_msg}
        except (ValueError, FileNotFoundError) as e:
            error_msg = f"PDF file not found: {e}"
            logger.error(error_msg)
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}

        # 3. SECTION SPLITTING
        sections = processor.detect_sections(text)
        
        # 4. Save Core Data & Mark Ready
        paper.full_text = sanitize_text(text)
        paper.sections = sanitize_text(sections)
        paper.processed = True
        paper.save()
        
        # 5. Trigger Async AI Tasks (Deep Analysis)
        details_task = identify_paper_details_task.delay(paper_id)
        embed_task = generate_embeddings_task.delay(paper_id)
        
        paper.task_ids['identify_details'] = details_task.id
        paper.task_ids['generate_embeddings'] = embed_task.id
        paper.save(update_fields=['task_ids'])
        
        update_task_status(task_id, 'completed', result={'message': 'PDF processed (AI running in background)'})
        return {'message': 'PDF processed'}
        
    except Exception as e:
        logger.error(f"PDF processing error for {paper_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def identify_paper_details_task(self, paper_id: str) -> Dict[str, Any]:
    """
    STAGE 2: AI METADATA EXTRACTION (Async).
    Extracts Title, Authors, Year using LLM.
    Updates the paper record silently without blocking UI.
    """
    try:
        paper = Paper.objects.get(id=paper_id)
        llm = LLMService()
        
        # Use first 6k chars
        context = paper.full_text[:6000] if paper.full_text else ""
        
        metadata_prompt = f"""Extract the following metadata from this research paper:
- Title (exact title)
- Authors (comma-separated list of author names)
- Year (publication year)
- Journal (publication venue)

Paper text:
{context}

Return ONLY valid JSON:
{{
  "title": "exact paper title",
  "authors": ["Author One", "Author Two"],
  "year": "2024",
  "journal": "Journal Name"
}}"""

        # Call LLM
        if llm.__class__.__name__ == 'GeminiLLMService':
            response = llm._generate(metadata_prompt)
            from services.llm_service import _parse_json_safe
            metadata = _parse_json_safe(response if response else "", {
                'title': paper.filename,
                'authors': [],
                'year': 'Unknown',
                'journal': 'Unknown'
            })
        else:
             # Fallback
             metadata = {'title': paper.filename, 'authors': [], 'year': 'Unknown'}

        # Update Paper
        # ROBUSTNESS: AI sometimes returns null for journal/year. 
        # We enforce "Unknown" to prevent DB constraint violations.
        paper.title = sanitize_text(metadata.get('title') or paper.filename)
        paper.authors = json.dumps(metadata.get('authors') or [])
        paper.year = sanitize_text(metadata.get('year') or 'Unknown')
        paper.journal = sanitize_text(metadata.get('journal') or 'Unknown')
        paper.save(update_fields=['title', 'authors', 'year', 'journal'])
        
        return metadata

    except Exception as e:
        logger.error(f"Metadata extraction failed for {paper_id}: {e}")
        return {'error': str(e)}

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def generate_embeddings_task(self, paper_id: str) -> Dict[str, str]:
    """
    STAGE 3: VECTOR EMBEDDINGS (Async).
    Generates semantic vectors for RAG.
    Heavy operation (can take 10-20s).
    """
    try:
        paper = Paper.objects.get(id=paper_id)
        embedding_service = EmbeddingService()
        embedding_service.store_embeddings(paper, paper.sections or {})
        return {'message': 'Embeddings generated'}
    except Exception as e:
        logger.error(f"Embedding generation failed for {paper_id}: {e}")
        return {'error': str(e)}

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def extract_methodology_task(self, paper_id: str) -> Dict[str, Any]:
    """
    EXTRACT TECHNICAL METHODOLOGY (Stage 2).
    This task is triggered by the user clicking the 'Methodology' button.
    It uses the LLM to analyze the 'Methodology' section and extract structured data.
    
    Args:
        paper_id: UUID of the Paper.
        
    Returns:
        Dict: Methodology fields or error message.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        if not paper.processed:
            error_msg = 'Paper must be processed first.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        sections = paper.sections or {}
        sections_lower = {k.lower(): v for k, v in sections.items()}
        
        # Look for methodology-related sections
        methodology_text = (
            sections_lower.get('methodology', '') or
            sections_lower.get('methods', '') or
            sections_lower.get('approach', '') or
            sections_lower.get('experimental setup', '')
        )[:5000]  # Limit context window
        
        if not methodology_text:
            error_msg = 'No methodology section found in paper. Try processing the PDF again.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        llm = LLMService()
        result = llm.extract_methodology(methodology_text)
        
        # Delete old methodology if it exists
        Methodology.objects.filter(paper=paper).delete()
        
        # Save new methodology
        methodology = Methodology.objects.create(
            paper=paper,
            datasets=sanitize_text(result['datasets']),
            model=sanitize_text(result['model']),
            metrics=sanitize_text(result['metrics']),
            results=sanitize_text(result['results']),
            summary=sanitize_text(result['summary'])
        )
        
        # Mark flag
        paper.methodology_status = True
        paper.save(update_fields=['methodology_status'])
        
        update_task_status(task_id, 'completed', result={'methodology_id': str(methodology.id)})
        return {'methodology_id': str(methodology.id)}
        
    except Paper.DoesNotExist:
        error_msg = f'Paper {paper_id} does not exist.'
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}
    except Exception as e:
        logger.error(f"Methodology extraction error for {paper_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def extract_all_sections_task(self, paper_id: str) -> Dict[str, str]:
    """
    SECTION-BY-SECTION SUMMARIZATION (Stage 3).
    Triggered when the user clicks 'Summary'. 
    Uses the LLM to create bullet-point summaries of Abstract, Intro, etc.
    
    Args:
        paper_id: UUID of the Paper.
        
    Returns:
        Dict: Confirmation or error message.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        if not paper.processed:
            error_msg = 'Paper not processed yet.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        sections = paper.sections or {}
        llm = LLMService()
        summaries_dict = llm.summarize_sections(sections, paper.full_text)
        
        # Delete existing section summaries
        SectionSummary.objects.filter(paper=paper).delete()
        
        # Create new section summaries
        for idx, (section_name, summary_text) in enumerate(summaries_dict.items()):
            SectionSummary.objects.create(
                paper=paper,
                section_name=sanitize_text(section_name),
                summary=sanitize_text(summary_text),
                order_index=idx
            )
        
        # Generate Global Summary
        try:
            full_context = '\n\n'.join([
                f"**{section_name}:**\n{summary_text}"
                for section_name, summary_text in summaries_dict.items()
            ])[:4000]
            
            global_summary_prompt = f"""Based on these section summaries, create a concise TL;DR (2-3 sentences) of the entire paper.

{full_context}

Return ONLY the TL;DR summary:"""
            
            if llm.__class__.__name__ == 'GeminiLLMService':
                # Gemini
                response = llm._generate(global_summary_prompt)
                # Gemini _generate returns Optional[str]
                global_summary = response if response else "Summary not available"
            elif llm.__class__.__name__ == 'OllamaLLMService':
                # Ollama
                global_summary = llm._generate(global_summary_prompt, json_mode=False)
            else:
                global_summary = "Summary not available"
            
            paper.global_summary = sanitize_text(global_summary)
            paper.save(update_fields=['global_summary'])
            
        except Exception as summary_error:
            logger.warning(f"Failed to generate global summary for paper {paper_id}: {summary_error}")
        
        update_task_status(task_id, 'completed', result={'message': 'Sections summarized'})
        return {'message': 'Sections summarized'}
        
    except Paper.DoesNotExist:
        error_msg = f'Paper {paper_id} does not exist.'
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}
    except Exception as e:
        logger.error(f"Section summarization error for {paper_id}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def extract_metadata_task(self, paper_id: str, field: str) -> Dict[str, Any]:
    """
    TARGETED METADATA EXTRACTION (Datasets, Licenses).
    This is called when the user clicks 'Datasets' or 'Licenses'.
    Uses SMART CONTEXT CROPPING to reduce LLM costs.
    
    Args:
        paper_id: UUID of the Paper.
        field: 'datasets' or 'licenses'.
        
    Returns:
        Dict: Extracted data or error message.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        paper = Paper.objects.get(id=paper_id)
        if not paper.processed:
            error_msg = 'Paper not processed yet.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        # CONTEXT WINDOW OPTIMIZATION STRATEGY
        sections = paper.sections or {}
        sections_lower = {k.lower(): v for k, v in sections.items()}
        
        # Build context with priority sections based on field
        priority_keys = ['abstract', 'introduction', 'methodology', 'methods', 'experiments', 'experimental setup']
        
        if field == 'datasets':
            priority_keys.extend(['datasets', 'datasets and metrics', 'evaluation', 'results', 'data availability'])
        elif field == 'licenses':
            priority_keys.extend(['availability', 'code availability', 'data availability', 'acknowledgments', 'license'])
            
        # Deduplicate keys while preserving order
        priority_keys = list(dict.fromkeys(priority_keys))
        
        context_parts = []
        for key in priority_keys:
            if key in sections_lower and sections_lower[key]:
                # Increase section limit to 5000 chars to capture more context
                context_parts.append(f"--- {key.upper()} ---\n{sections_lower[key][:5000]}")
        
        # Join and cap at 30,000 chars (Gemini has large context window)
        context = '\n\n'.join(context_parts)[:30000]
        
        if len(context) < 1000:
            # Fallback to full text if no sections found or context is too small
            # Use first 30k chars which usually covers most of the paper
            context = paper.full_text[:30000] if paper.full_text else ''
        
        if not context:
            error_msg = f'No meaningful text to extract {field}.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        llm = LLMService()
        
        if field == 'datasets':
            prompt = f"""Analyze the following paper text and list ALL datasets, databases, or data benchmarks used or created.
Be thorough. If a dataset is mentioned by name (e.g., "ImageNet", "CoNLL-2003"), include it.
Return ONLY a JSON array of strings. If absolutely no datasets are mentioned, return ["None mentioned"].

Paper Text:
{context}

Return format: ["dataset1", "dataset2"]"""
        elif field == 'licenses':
            prompt = f"""Analyze the following paper text and list ALL software licenses or data usage terms mentioned.
Look for "MIT", "Apache", "CC-BY", "GPL", or custom terms like "Research Use Only".
Return ONLY a JSON array of strings. If absolutely no licenses are mentioned, return ["None mentioned"].

Paper Text:
{context}

Return format: ["license1", "license2"]"""
        else:
            error_msg = f'Invalid field: {field}'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        # Execute LLM call
        llm_class_name = llm.__class__.__name__
        logger.info(f"Extracting {field} using LLM Class: {llm_class_name}")

        if llm_class_name == 'GeminiLLMService':
            # Gemini
            logger.info(f"Generating metadata for {field} using Gemini...")
            try:
                response = llm._generate(prompt)
                logger.info(f"Gemini Raw Response for {field} (Type: {type(response)}): {response}")
                
                from services.llm_service import _parse_json_safe
                response_text = response if response else ""
                
                if not response:
                    logger.warning(f"Gemini returned empty response for {field}")
                
                result = _parse_json_safe(response_text, ["None mentioned"])
                logger.info(f"Parsed Result for {field}: {result}")
            except Exception as e:
                logger.error(f"Error during Gemini generation for {field}: {e}", exc_info=True)
                result = ["None mentioned"]

        elif llm_class_name == 'OllamaLLMService':
            # Ollama
            logger.info(f"Generating metadata for {field} using Ollama...")
            response_text = llm._generate(prompt, json_mode=True)
            from services.llm_service import _parse_json_safe
            result = _parse_json_safe(response_text, ["None mentioned"])
        else:
            logger.warning(f"Unknown LLM Class: {llm_class_name}. Falling back.")
            result = ["None mentioned"]
        
        if not isinstance(result, list):
            result = ["None mentioned"]
        
        # Save to metadata
        paper.metadata[field] = sanitize_text(result)
        paper.save(update_fields=['metadata'])
        
        update_task_status(task_id, 'completed', result={field: result})
        return {field: result}
        
    except Paper.DoesNotExist:
        error_msg = f'Paper {paper_id} does not exist.'
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}
    except Exception as e:
        logger.error(f"Metadata extraction error for {paper_id}/{field}: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        raise

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def analyze_collection_gaps_task(self, collection_id: str) -> Dict[str, str]:
    """
    MULTI-PAPER RESEARCH GAP ANALYSIS (Map-Reduce Pattern).
    
    Analyzes multiple papers in a collection to identify research gaps.
    This demonstrates multi-document reasoning, a key skill for senior AI roles.
    
    Map Phase: Extract conclusions/future work from each paper
    Reduce Phase: LLM synthesizes common gaps
    
    Args:
        collection_id: UUID of the Collection.
        
    Returns:
        Dict: Gap analysis result with 'gap_analysis' key.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        from .models import Collection
        from django.utils import timezone
        
        collection = Collection.objects.get(id=collection_id)
        papers = collection.papers.filter(processed=True)
        
        if papers.count() < 2:
            error_msg = "Need at least 2 processed papers for gap analysis."
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        # MAP PHASE: Extract relevant sections from each paper
        paper_contexts = []
        for paper in papers:
            sections = paper.sections or {}
            sections_lower = {k.lower(): v for k, v in sections.items()}
            
            # Extract key sections
            future_work = (
                sections_lower.get('future work', '') or
                sections_lower.get('future directions', '') or
                sections_lower.get('discussion', '')[:2000]
            )
            
            conclusion = (
                sections_lower.get('conclusion', '') or
                sections_lower.get('conclusions', '') or
                paper.full_text[-3000:] if paper.full_text else ''
            )
            
            limitations = sections_lower.get('limitations', '')
            
            paper_contexts.append({
                'title': paper.title or paper.filename,
                'future_work': future_work[:3000],
                'conclusion': conclusion[:3000],
                'limitations': limitations[:2000]
            })
        
        # REDUCE PHASE: LLM synthesis
        llm = LLMService()
        gap_analysis = llm.analyze_research_gaps(paper_contexts)
        
        # Save to collection
        collection.gap_analysis = sanitize_text(gap_analysis)
        collection.gap_analysis_updated_at = timezone.now()
        collection.save(update_fields=['gap_analysis', 'gap_analysis_updated_at'])
        
        update_task_status(task_id, 'completed', result={'gap_analysis': gap_analysis})
        return {'gap_analysis': gap_analysis}
        
    except Exception as e:
        logger.error(f"Gap analysis error for collection {collection_id}: {e}")
        error_msg = str(e)
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def analyze_swot_task(self, paper_id: str) -> Dict[str, str]:
    """
    SWOT ANALYSIS FOR INDIVIDUAL PAPERS.
    
    Analyzes a single paper to identify Strengths, Weaknesses, Opportunities, and Threats.
    Provides researchers with a structured framework to evaluate research papers.
    
    Args:
        paper_id: UUID of the Paper.
        
    Returns:
        Dict: SWOT analysis result.
    """
    task_id = self.request.id
    update_task_status(task_id, 'running')
    
    try:
        from django.utils import timezone
        
        paper = Paper.objects.get(id=paper_id)
        if not paper.processed:
            error_msg = 'Paper not processed yet.'
            update_task_status(task_id, 'failed', error=error_msg)
            return {'error': error_msg}
        
        # Build context from key sections
        sections = paper.sections or {}
        sections_lower = {k.lower(): v for k, v in sections.items()}
        
        context_parts = [
            f"**Title:** {paper.title or paper.filename}",
            f"**Authors:** {paper.authors}",
        ]
        
        # Add key sections
        for section_key in ['abstract', 'introduction', 'methodology', 'methods', 'conclusion', 'results']:
            if section_key in sections_lower and sections_lower[section_key]:
                context_parts.append(f"**{section_key.title()}:**\n{sections_lower[section_key][:2000]}")
        
        paper_context = '\n\n'.join(context_parts)
        
        # Call LLM
        llm = LLMService()
        swot_analysis = llm.analyze_swot(paper_context)
        
        # Save to paper
        paper.swot_analysis = sanitize_text(swot_analysis)
        paper.swot_analysis_updated_at = timezone.now()
        paper.save(update_fields=['swot_analysis', 'swot_analysis_updated_at'])
        
        update_task_status(task_id, 'completed', result={'swot_analysis': swot_analysis})
        return {'swot_analysis': swot_analysis}
        
    except Paper.DoesNotExist:
        error_msg = f'Paper {paper_id} does not exist.'
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}
    except Exception as e:
        logger.error(f"SWOT analysis error for paper {paper_id}: {e}")
        error_msg = str(e)
        update_task_status(task_id, 'failed', error=error_msg)
        return {'error': error_msg}
