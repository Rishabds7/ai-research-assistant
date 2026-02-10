"""
EMBEDDING & VECTOR SEARCH SERVICE (Google Cloud Optimized)
Project: Research Assistant
File: backend/services/embedding_service.py

This service handles converting text into numerical vectors (Embeddings)
using Google's 'gemini-embedding-001' model. 

BENEFITS:
- Cloud-based: No local RAM/GPU required (saves $30/mo on Render).
- High Performance: 768-dimensional semantic density.
- Cost: Free tier supported via Gemini API Key.
"""

import logging
import tiktoken
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from django.conf import settings
from pgvector.django import CosineDistance

from papers.models import Embedding as EmbeddingModel

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Logic for Vector Operations using Google Generative AI.
    Handles embedding generation, storage, and semantic search.
    """
    def __init__(self) -> None:
        """
        Initializes the EmbeddingService with Google Gemini configuration.
        """
        # Configure the API key from settings
        if not settings.GEMINI_API_KEY:
            logger.error("CRITICAL: GEMINI_API_KEY is missing! Check your environment variables.")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Default to the most stable model as of Feb 2026
        # We use text-embedding-004 because it supports setting output_dimensionality
        self.model_name = "models/text-embedding-004"
        self._model_confirmed = False

    def _ensure_model(self) -> None:
        """
        Ensures we have a working model if we haven't already confirmed one.
        Iterates through a priority list of models to find a working one.
        """
        if self._model_confirmed:
            return

        test_text = "test"
        # Use 768-dimension models for optimal performance
        models_to_try = [
            "models/text-embedding-004", # Priority 1 (Supports 768 dims)
            "models/gemini-embedding-001", # Priority 2 (Native 768 dims)
            "models/embedding-001"         # Priority 3 (Legacy)
        ]
        
        for model in models_to_try:
            try:
                # Force 768 dimensions for all models
                genai.embed_content(
                    model=model, 
                    content=test_text, 
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                self.model_name = model
                self._model_confirmed = True
                logger.info(f"EMBEDDING: Confirmed working model: {model} (Force 768 Dims)")
                return
            except Exception:
                try:
                    # Fallback for models that don't support output_dimensionality
                    genai.embed_content(model=model, content=test_text, task_type="retrieval_document")
                    self.model_name = model
                    self._model_confirmed = True
                    logger.info(f"EMBEDDING: Confirmed working model: {model} (Native Dims)")
                    return
                except Exception:
                    continue
        
    def generate_embedding(self, text: str) -> List[float]:
        """
        Calls Google's Embedding API with fallback models.
        Returns a 768-length vector.
        
        Args:
            text: The text content to embed.
            
        Returns:
            List[float]: A list of floats representing the embedding vector.
        """
        if not text.strip():
            return []
            
        self._ensure_model()
        
        try:
            # Prepare kwargs - add dimensionality for new models
            kwargs = {
                "model": self.model_name,
                "content": text,
                "task_type": "retrieval_document",
                "title": "Research Paper Chunk",
                "output_dimensionality": 768 # Force 768
            }

            result = genai.embed_content(**kwargs)
            
            # Validation check
            embedding = result['embedding']
            if len(embedding) != 768:
                logger.warning(f"EMBEDDING MISMATCH: Got {len(embedding)} dims, expected 768. Truncating/Padding.")
                if len(embedding) > 768:
                    embedding = embedding[:768]
                else:
                    embedding = embedding + [0.0] * (768 - len(embedding))
                
            return embedding
        except Exception as e:
            logger.error(f"Google Embedding Error (model {self.model_name}): {e}")
            # Final desperate fallback attempt
            try:
                result = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=text,
                    task_type="retrieval_document"
                )
                return result['embedding']
            except Exception:
                return []

    def _chunk_text(self, text: str, max_tokens: int = 800, overlap: int = 150) -> List[str]:
        """
        Robust Token-based splitting with Overlap.
        
        Logic:
        1. Try to split by Paragraphs (\n\n).
        2. If a chunk is still too big, try to split by Sentences (. ).
        3. If still too big, use a sliding window of tokens with overlap.
        
        This preserves semantic meaning better than hard character cuts.
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to a simpler encoding if something goes wrong
            encoding = tiktoken.get_encoding("gpt2")
            
        def count_tokens(t: str) -> int:
            return len(encoding.encode(t))

        if count_tokens(text) <= max_tokens:
            return [text.strip()]

        chunks = []
        # Step 1: Split into paragraphs
        paragraphs = text.split('\n\n')
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)
            
            # If a single paragraph is larger than max_tokens, we must split it further
            if para_tokens > max_tokens:
                # First, save what we have
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # Split paragraph by sentences
                sentences = para.replace('. ', '.[SPLIT]').split('[SPLIT]')
                for sent in sentences:
                    sent_tokens = count_tokens(sent)
                    if sent_tokens > max_tokens:
                        # Hard token split with overlap (Last resort)
                        tokens = encoding.encode(sent)
                        for i in range(0, len(tokens), max_tokens - overlap):
                            part_tokens = tokens[i:i + max_tokens]
                            chunks.append(encoding.decode(part_tokens))
                    else:
                        if current_tokens + sent_tokens > max_tokens:
                            chunks.append("\n\n".join(current_chunk))
                            current_chunk = [sent]
                            current_tokens = sent_tokens
                        else:
                            current_chunk.append(sent)
                            current_tokens += sent_tokens
            else:
                # Standard paragraph accumulation
                if current_tokens + para_tokens > max_tokens:
                    chunks.append("\n\n".join(current_chunk))
                    # Basic overlap: Include the last part of previous chunk if possible
                    # For simplicity in this manual implementation, we just start fresh
                    # But the 'sliding window' fallback above handles the true overlap.
                    current_chunk = [para]
                    current_tokens = para_tokens
                else:
                    current_chunk.append(para)
                    current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # Add explicit sliding window overlap to all chunks to ensure context continuity
        # This is what's missing in simple splitters
        refined_chunks = []
        for i, content in enumerate(chunks):
            if i == 0:
                refined_chunks.append(content)
                continue
            
            # Add a bit of the previous chunk to the start of this one
            prev_content = chunks[i-1]
            prev_tokens = encoding.encode(prev_content)
            overlap_text = encoding.decode(prev_tokens[-overlap:])
            refined_chunks.append(f"...{overlap_text}\n{content}")
            
        return refined_chunks

    def store_embeddings(self, paper_instance: Any, sections: Dict[str, str]) -> None:
        """
        Splits paper into chunks using token-based semantic splitting and stores them.
        """
        # Ensure we have a working model first
        self._ensure_model()
        
        # Clear existing
        EmbeddingModel.objects.filter(paper=paper_instance).delete()
        
        all_chunks = []
        for section_name, text in sections.items():
            if not text.strip(): continue
            
            # Use our new robust token-based chunker
            section_chunks = self._chunk_text(text, max_tokens=800, overlap=150)
            
            for content in section_chunks:
                if len(content.strip()) < 20: continue
                all_chunks.append({"section": section_name, "text": content})

        if not all_chunks:
            return

        logger.info(f"Generating embeddings for {len(all_chunks)} chunks in batches using {self.model_name}...")
        
        embeddings_to_create = []
        # Google API supports batching multiple contents in one call
        BATCH_SIZE = 50 
        
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i:i+BATCH_SIZE]
            batch_texts = [item["text"] for item in batch]
            
            try:
                # Use batch_embed_contents for massive speedup
                kwargs = {
                    "model": self.model_name,
                    "content": batch_texts,
                    "task_type": "retrieval_document"
                }
                
                if "text-embedding-004" in self.model_name:
                    kwargs["output_dimensionality"] = 768

                result = genai.embed_content(**kwargs)
                
                for idx, vec in enumerate(result['embedding']):
                    # Robust handling of dimension mismatch
                    if len(vec) != 768:
                        logger.warning(f"Batch dimension mismatch: {len(vec)}. Truncating/Padding to 768.")
                        if len(vec) > 768:
                            vec = vec[:768]
                        else:
                            vec = vec + [0.0] * (768 - len(vec))
                        
                    embeddings_to_create.append(
                        EmbeddingModel(
                            paper=paper_instance,
                            section_name=batch[idx]["section"],
                            text=batch[idx]["text"],
                            embedding=vec
                        )
                    )
            except Exception as e:
                logger.error(f"Batch Embedding Error at index {i} with {self.model_name}: {e}")
                
                # Fallback: try individual if batch fails (rare)
                for item in batch:
                    try:
                        vec = self.generate_embedding(item["text"])
                        if vec:
                            embeddings_to_create.append(
                                EmbeddingModel(
                                    paper=paper_instance,
                                    section_name=item["section"],
                                    text=item["text"],
                                    embedding=vec
                                )
                            )
                    except Exception:
                        continue

        if embeddings_to_create:
            EmbeddingModel.objects.bulk_create(embeddings_to_create, batch_size=100)
            logger.info(f"Successfully stored {len(embeddings_to_create)} embeddings.")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search using Google's embedding for the query.
        
        Args:
            query: The search query string.
            k: Number of results to return.
            
        Returns:
            List[Dict[str, Any]]: List of search results with metadata and distance.
        """
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query",
                output_dimensionality=768 # Force 768 for search too
            )
            query_vec = result['embedding']
            if len(query_vec) != 768:
                query_vec = query_vec[:768] if len(query_vec) > 768 else query_vec + [0.0] * (768 - len(query_vec))
        except Exception as e:
            logger.error(f"Google Search Embedding Error: {e}")
            return []

        # Find closest matches in DB using pgvector
        results = EmbeddingModel.objects.alias(
            distance=CosineDistance('embedding', query_vec)
        ).order_by('distance')[:k]

        return [
            {
                "paper_id": str(r.paper.id),
                "paper_filename": r.paper.filename,
                "section": r.section_name,
                "text": r.text,
                "distance": getattr(r, 'distance', 0.0) 
            }
            for r in results
        ]
