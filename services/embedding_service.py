"""
Embedding and vector search service using sentence-transformers and FAISS.
Chunks text, embeds with all-MiniLM-L6-v2, and indexes with FAISS (IndexFlatL2, dim=384).
"""

from typing import Any, Optional

import faiss
from sentence_transformers import SentenceTransformer

from config.settings import EMBEDDING_MODEL

# all-MiniLM-L6-v2 output dimension
EMBEDDING_DIM = 384
CHUNK_SIZE = 500


class EmbeddingService:
    """
    Embed text with sentence-transformers and search with FAISS.
    Keeps metadata: paper_id, section, text per index.
    """

    def __init__(self) -> None:
        """Load embedding model and create empty FAISS index (IndexFlatL2, dim=384)."""
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
        # Metadata: FAISS index position -> {paper_id, section, text}
        self.metadata: dict[int, dict[str, Any]] = {}

    def chunk_text(
        self, text: str, section: str, paper_id: str
    ) -> list[dict[str, Any]]:
        """
        Split text into chunks of ~500 characters with overlap for context.

        Args:
            text: Section or full text to chunk.
            section: Section name (e.g. methodology).
            paper_id: Paper identifier.

        Returns:
            List of dicts: {"text": chunk, "section": section, "paper_id": paper_id}.
        """
        chunks: list[dict[str, Any]] = []
        start = 0
        text = text.strip()
        if not text:
            return chunks

        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            # Prefer breaking at sentence or word boundary
            if end < len(text):
                for sep in (". ", "\n", " "):
                    last = text.rfind(sep, start, end + 1)
                    if last > start:
                        end = last + len(sep)
                        break
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "text": chunk_text,
                        "section": section,
                        "paper_id": paper_id,
                    }
                )
            start = end

        return chunks

    def add_paper(self, sections_dict: dict[str, str], paper_id: str) -> None:
        """
        Chunk all sections, embed, and add vectors to FAISS.
        Updates metadata for each added chunk.

        Args:
            sections_dict: Dict mapping section name to section text.
            paper_id: Unique paper identifier.
        """
        all_chunks: list[dict[str, Any]] = []
        for section, text in sections_dict.items():
            all_chunks.extend(self.chunk_text(text, section, paper_id))

        if not all_chunks:
            return

        texts = [c["text"] for c in all_chunks]
        embeddings = self.model.encode(texts).astype("float32")

        # FAISS assigns new vectors indices ntotal, ntotal+1, ...
        start_id = self.index.ntotal
        for i, chunk in enumerate(all_chunks):
            self.metadata[start_id + i] = {
                "paper_id": paper_id,
                "section": chunk["section"],
                "text": chunk["text"],
            }
        self.index.add(embeddings)

    def search(
        self,
        query: str,
        k: int = 5,
        section_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Embed query, search FAISS, return top-k chunks with metadata.
        Optionally filter by section after search.

        Args:
            query: Search query string.
            k: Number of results to return.
            section_filter: If set, only return chunks from this section.

        Returns:
            List of dicts with keys: paper_id, section, text, (optional) distance.
        """
        if self.index.ntotal == 0:
            return []

        q_embedding = self.model.encode([query]).astype("float32")
        # Search more if we will filter by section
        fetch_k = k * 3 if section_filter else k
        fetch_k = min(fetch_k, self.index.ntotal)

        distances, indices = self.index.search(q_embedding, fetch_k)
        results: list[dict[str, Any]] = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx < 0:
                continue
            meta = self.metadata.get(idx)
            if not meta:
                continue
            if section_filter and meta.get("section") != section_filter:
                continue
            results.append(
                {
                    "paper_id": meta["paper_id"],
                    "section": meta["section"],
                    "text": meta["text"],
                    "distance": float(dist),
                }
            )
            if len(results) >= k:
                break

        return results
