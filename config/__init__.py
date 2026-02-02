"""Configuration package."""

from config.settings import (
    DATA_DIR,
    EMBEDDING_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PROCESSED_DIR,
    UPLOADS_DIR,
    ensure_dirs,
)

__all__ = [
    "DATA_DIR",
    "EMBEDDING_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "PROCESSED_DIR",
    "UPLOADS_DIR",
    "ensure_dirs",
]
