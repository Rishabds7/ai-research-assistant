"""
Configuration management for the Research Paper Analysis MVP.
Loads environment variables and defines paths and constants.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API and model constants
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Default to a model that supports generateContent (e.g. gemini-2.0-flash). Override with GEMINI_MODEL in .env.
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

# LLM Selection
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "ollama"
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# Base paths (relative to project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR: Path = _PROJECT_ROOT / "data"
UPLOADS_DIR: Path = DATA_DIR / "uploads"
PROCESSED_DIR: Path = DATA_DIR / "processed"


def ensure_dirs() -> None:
    """Create data directories if they do not exist."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
