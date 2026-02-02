"""
PDF processing service using PyMuPDF (fitz).
Extracts text and detects paper sections (Abstract, Introduction, etc.).
"""

import json
import re
from pathlib import Path
from typing import Any, Union

import fitz

from config.settings import PROCESSED_DIR, ensure_dirs


class PDFProcessor:
    """Process PDF research papers: extract text and detect sections."""

    # Section headers to detect (case-insensitive)
    SECTION_PATTERNS = [
        "abstract",
        "introduction",
        "background",
        "related work",
        "literature review",
        "methodology",
        "method",
        "approach",
        "experiments",
        "experimental setup",
        "results",
        "evaluation",
        "discussion",
        "conclusion",
        "future work",
    ]

    def __init__(self) -> None:
        """Initialize processor and ensure output directory exists."""
        ensure_dirs()

    def extract_text(self, pdf_path: Union[Path, str]) -> str:
        """
        Extract all text from a PDF using PyMuPDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Concatenated text from all pages.

        Raises:
            ValueError: If PDF is corrupted, empty, or cannot be opened.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise ValueError(f"PDF file not found: {path}")

        try:
            doc = fitz.open(path)
        except Exception as e:
            raise ValueError(f"Could not open PDF: {e}") from e

        try:
            text_parts: list[str] = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            full_text = "\n".join(text_parts).strip()
            if not full_text:
                raise ValueError("PDF contains no extractable text")
            return full_text
        except ValueError:
            raise
        except Exception as e:
            doc.close()
            raise ValueError(f"Error extracting text: {e}") from e

    def detect_sections(self, text: str) -> dict[str, str]:
        """
        Detect paper sections using regex (case-insensitive).
        Looks for: abstract, introduction, methodology, method, results, conclusion.

        Args:
            text: Full document text.

        Returns:
            Dict mapping section name to section text. Keys are lowercase.
        """
        sections: dict[str, str] = {}
        text_lower = text.lower()

        # Build regex: match section headers (at line start or after newline)
        for section_name in self.SECTION_PATTERNS:
            # Match "Section Name" or "1. Section Name" at start of line
            pattern = rf"(?:\n|^)\s*(?:\d+\.?\s*)?{re.escape(section_name)}\s*\n"
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                start = match.end()
                # Find next section or end of text
                next_section_start = len(text)
                for other in self.SECTION_PATTERNS:
                    if other == section_name:
                        continue
                    pat = rf"\n\s*(?:\d+\.?\s*)?{re.escape(other)}\s*\n"
                    m = re.search(pat, text_lower[start:], re.IGNORECASE)
                    if m:
                        candidate = start + m.start()
                        if candidate < next_section_start:
                            next_section_start = candidate
                section_text = text[start:next_section_start].strip()
                if section_text:
                    sections[section_name] = section_text

        return sections

    def process_pdf(self, pdf_path: Union[Path, str], paper_id: str) -> dict[str, Any]:
        """
        Extract text, detect sections, and save result to JSON in data/processed/.

        Args:
            pdf_path: Path to the PDF file.
            paper_id: Unique identifier for the paper.

        Returns:
            Dict with keys: paper_id, full_text, sections, and optionally file path.
        """
        path = Path(pdf_path)
        full_text = self.extract_text(path)
        sections = self.detect_sections(full_text)

        result = {
            "paper_id": paper_id,
            "full_text": full_text,
            "sections": sections,
        }

        # Save to processed dir
        out_path = PROCESSED_DIR / f"{paper_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        result["processed_path"] = str(out_path)
        return result
