"""
EMBEDDING & VECTOR SEARCH SERVICE
Project: Research Assistant
File: backend/services/embedding_service.py

This service handles converting text into numerical vectors (Embeddings).
It enables the 'Search' and 'Side-by-side RAG' features.
Uses the 'all-MiniLM-L6-v2' model which is optimized for speed and semantic accuracy.

AI INTERVIEW FOCUS:
- Dimensionality: The model produces 384-dimensional vectors.
- RAG (Retrieval-Augmented Generation): This service is the 'Retrieval' part. 
  It finds relevant text chunks that are then injected into LLM prompts.
- pgvector: We use specialized PostgreSQL extensions to perform vector math 
  directly in the database for high-performance similarity search.
"""

from typing import List, Dict, Any
from django.conf import settings
from pgvector.django import CosineDistance

from papers.models import Embedding as EmbeddingModel

# Load transformer model once at module level to avoid re-loading on every request.
# Loading can take 2-5 seconds, so we use a singleton pattern.
_model = None

def get_model():
    """
    Singleton getter for the SentenceTransformer model.
    Ensures the model is only loaded into memory once per process (worker).
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

class EmbeddingService:
    """
    Core Logic for Vector Operations.
    Provides methods to generate, store, and search against high-dimensional vectors.
    """
    def __init__(self):
        # Model will be loaded on first use via get_model()
        pass

    def generate_embedding(self, text: str) -> List[float]:
        """
        CONVERT TEXT TO MATH.
        
        Args:
            text: A string of text (sentence or paragraph).
            
        Returns:
            A list of floats representing the semantic position of the text in latent space.
            The 'all-MiniLM-L6-v2' model creates a 384-length vector.
        """
        if not text.strip():
            return []
        model = get_model()
        # Enforce conversion to list so it can be stored in the DB vector field
        return model.encode(text).tolist()

    def store_embeddings(self, paper_instance, sections: Dict[str, str], chunk_size: int = 500):
        """
        VECTORIZATION PIPELINE.
        
        This translates a structured paper (dict of sections) into searchable chunks.
        
        Strategy:
        1. Clean and chunk the text. LLMs have contact window limits, and vector search 
           is most accurate when chunks are concise and thematic.
        2. Generate one embedding per chunk.
        3. Batch insert into PostgreSQL for database efficiency.
        """
        # Clear existing embeddings to ensure data freshness on re-processing
        EmbeddingModel.objects.filter(paper=paper_instance).delete()
        
        embeddings_to_create = []

        for section_name, text in sections.items():
            # Paragraph-aware chunking: preserves semantic boundaries better than fixed-length splits
            paragraphs = text.split('\n\n')
            
            for para in paragraphs:
                if not para.strip():
                    continue
                    
                # Overflow handling: if a paragraph is abnormally large, force a split
                if len(para) > chunk_size * 2:
                   for i in range(0, len(para), chunk_size):
                       chunk = para[i:i + chunk_size]
                       vec = self.generate_embedding(chunk)
                       if vec:
                           embeddings_to_create.append(
                               EmbeddingModel(
                                   paper=paper_instance,
                                   section_name=section_name,
                                   text=chunk,
                                   embedding=vec
                               )
                           )
                else:
                    vec = self.generate_embedding(para)
                    if vec:
                        embeddings_to_create.append(
                            EmbeddingModel(
                                paper=paper_instance,
                                section_name=section_name,
                                text=para,
                                embedding=vec
                            )
                        )
        
        # Performance: bulk_create is ~10-20x faster than individual .save() calls
        EmbeddingModel.objects.bulk_create(embeddings_to_create, batch_size=100)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        SEMANTIC SEARCH (THE 'R' IN RAG).
        
        Uses Cosine Similarity to find the k most relevant chunks relative to a query.
        
        Technical Detail:
        - We convert the user's natural language query into the SAME vector space 
          as the papers.
        - We then use pgvector's 'CosineDistance' logic to rank chunks.
        
        Args:
            query: Natural language string (e.g. "What is the training dataset?")
            k: Number of top matches to return.
        """
        query_vec = self.generate_embedding(query)
        if not query_vec:
            return []

        # SEARCH LOGIC:
        # Cosine Distance (ranked 0.0 to 2.0). 
        # 0.0 means identical; 1.0 means unrelated.
        # k=5 is the 'Golden Mean'—enough context to answer accurately, 
        # but small enough to fit in the LLM's prompt window.
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
