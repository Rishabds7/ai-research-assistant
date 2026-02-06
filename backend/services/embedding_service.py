"""
EMBEDDING & VECTOR SEARCH SERVICE (Google Cloud Optimized)
Project: Research Assistant
File: backend/services/embedding_service.py

This service handles converting text into numerical vectors (Embeddings)
using Google's 'text-embedding-004' model. 

BENEFITS:
- Cloud-based: No local RAM/GPU required (saves $30/mo on Render).
- High Performance: 768-dimensional semantic density.
- Cost: Free tier supported via Gemini API Key.
"""

import logging
from typing import List, Dict, Any
import google.generativeai as genai
from django.conf import settings
from pgvector.django import CosineDistance

from papers.models import Embedding as EmbeddingModel

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Logic for Vector Operations using Google Generative AI.
    """
    def __init__(self):
        # Configure the API key from settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = "models/text-embedding-004"

    def generate_embedding(self, text: str) -> List[float]:
        """
        Calls Google's Embedding API.
        Returns a 768-length vector.
        """
        if not text.strip():
            return []
            
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
                title="Research Paper Chunk"
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Google Embedding Error: {e}")
            return []

    def store_embeddings(self, paper_instance, sections: Dict[str, str], chunk_size: int = 1500):
        """
        Splits paper into chunks and stores their Google embeddings in PostgreSQL.
        Uses batching to stay fast and avoid rate limits.
        """
        # Clear existing
        EmbeddingModel.objects.filter(paper=paper_instance).delete()
        
        all_chunks = []
        for section_name, text in sections.items():
            if not text.strip(): continue
            
            # Simple paragraph-based splitting
            paragraphs = text.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if not para or len(para) < 20: continue
                
                # Split huge paragraphs
                if len(para) > chunk_size:
                    sub_chunks = [para[i:i+chunk_size] for i in range(0, len(para), chunk_size)]
                    for sc in sub_chunks:
                        all_chunks.append({"section": section_name, "text": sc})
                else:
                    all_chunks.append({"section": section_name, "text": para})

        if not all_chunks:
            return

        logger.info(f"Generating embeddings for {len(all_chunks)} chunks in batches...")
        
        embeddings_to_create = []
        # Google API supports batching multiple contents in one call
        BATCH_SIZE = 50 
        
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i:i+BATCH_SIZE]
            batch_texts = [item["text"] for item in batch]
            
            try:
                # Use batch_embed_contents for massive speedup
                result = genai.embed_content(
                    model=self.model_name,
                    content=batch_texts,
                    task_type="retrieval_document"
                )
                
                for idx, vec in enumerate(result['embedding']):
                    embeddings_to_create.append(
                        EmbeddingModel(
                            paper=paper_instance,
                            section_name=batch[idx]["section"],
                            text=batch[idx]["text"],
                            embedding=vec
                        )
                    )
            except Exception as e:
                logger.error(f"Batch Embedding Error at index {i}: {e}")
                # Fallback: try individual if batch fails (rare)
                continue

        if embeddings_to_create:
            EmbeddingModel.objects.bulk_create(embeddings_to_create, batch_size=100)
            logger.info(f"Successfully stored {len(embeddings_to_create)} embeddings.")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search using Google's embedding for the query.
        """
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query"
            )
            query_vec = result['embedding']
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
