"""
Embedding service using SentenceTransformers and pgvector.
"""

from typing import List, Dict, Any
from django.conf import settings
from pgvector.django import CosineDistance

from papers.models import Embedding as EmbeddingModel

# Load model once at module level (lazy loading behavior in Django/Celery)
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

class EmbeddingService:
    def __init__(self):
        # Model will be loaded on first use
        pass

    def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text."""
        if not text.strip():
            return []
        model = get_model()
        return model.encode(text).tolist()

    def store_embeddings(self, paper_instance, sections: Dict[str, str], chunk_size: int = 500):
        """
        Generate and store embeddings for paper sections.
        
        Args:
            paper_instance: Paper model instance
            sections: Dict of section name -> text
            chunk_size: Approximate characters per chunk (splitting by paragraphs mostly)
        """
        # Clear existing embeddings for this paper
        EmbeddingModel.objects.filter(paper=paper_instance).delete()
        
        embeddings_to_create = []

        for section_name, text in sections.items():
            # Simple chunking strategy: split by paragraphs, then combine/split
            paragraphs = text.split('\n\n')
            
            for para in paragraphs:
                if not para.strip():
                    continue
                    
                # If paragraph is too long, strictly chunk it
                if len(para) > chunk_size * 2:
                   # Chunk large paragraph
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
        
        # Batch insert
        EmbeddingModel.objects.bulk_create(embeddings_to_create, batch_size=100)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search using pgvector.
        
        Returns:
            List of dicts with keys: paper_id, section, text, distance
        """
        query_vec = self.generate_embedding(query)
        if not query_vec:
            return []

        # Perform cosine distance search
        # Note: pgvector uses <=> for cosine distance (lower is better)
        # We limit to k results
        results = EmbeddingModel.objects.alias(
            distance=CosineDistance('embedding', query_vec)
        ).order_by('distance')[:k]

        return [
            {
                "paper_id": str(r.paper.id),
                "paper_filename": r.paper.filename,
                "section": r.section_name,
                "text": r.text,
                "distance": getattr(r, 'distance', 0.0) # distance might need explicit annotation in query
            }
            for r in results
        ]
