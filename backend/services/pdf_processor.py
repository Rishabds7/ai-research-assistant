"""
PDF processing service using PyMuPDF (fitz).
Extracts text and detects paper sections (Abstract, Introduction, etc.).
"""

import json
import re
from pathlib import Path
from typing import Any, Union

import fitz

class PDFProcessor:
    """Process PDF research papers: extract text and detect sections."""

    # Section headers to detect (case-insensitive)
    SECTION_PATTERNS = [
        "abstract",
        "introduction",
        "background",
        "related work",
        "literature review",
        "preliminaries",
        "problem statement",
        "methodology",
        "method",
        "proposed method",
        "proposed approach",
        "analytical model",
        "system model",
        "architecture",
        "system design",
        "implementation",
        "experiments",
        "experimental setup",
        "experimental design",
        "evaluation",
        "results",
        "performance analysis",
        "discussion",
        "conclusion",
        "conclusions",
        "future work",
        "summary",
        "acknowledgments",
        "references"
    ]

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
        Always combines predefined patterns with discovered numbered headers.
        """
        sections: dict[str, str] = {}
        text_lower = text.lower()
        
        # 1. First, find all potential numbered headers (e.g., "1. Introduction", "2 Related Work")
        # This catches custom-named methodology sections like "3. GRAPHRAG"
        generic_header_pat = r"(?:\n|^)(\d+\.?\s+([A-Z][A-Za-z\s]{3,50}))\s*(?:\n|$)"
        matches = list(re.finditer(generic_header_pat, text))
        
        discovered_headers = []
        for i, match in enumerate(matches):
            title = match.group(2).strip()
            start = match.end()
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            content = text[start:end].strip()
            if content:
                discovered_headers.append({
                    "title": title,
                    "content": content,
                    "start": match.start()
                })

        # 2. Check predefined patterns to ensure standard names are correctly labeled
        for section_name in self.SECTION_PATTERNS:
            pattern = rf"(?:\n|^)\s*(?:\d+\.?\s*)?{re.escape(section_name)}\s*(?:\n|$)"
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                start = match.end()
                # Find the next section start using either patterns or discovered headers
                next_start = len(text)
                
                # Check other patterns
                for other in self.SECTION_PATTERNS:
                    if other == section_name: continue
                    p = rf"\n\s*(?:\d+\.?\s*)?{re.escape(other)}\s*(?:\n|$)"
                    m = re.search(p, text_lower[start:], re.IGNORECASE)
                    if m:
                        cand = start + m.start()
                        if cand < next_start: next_start = cand
                
                # Check discovered headers
                for dh in discovered_headers:
                    if dh["start"] > match.start() and dh["start"] < next_start:
                        next_start = dh["start"]
                
                content = text[start:next_start].strip()
                if content:
                    sections[section_name.title()] = content

        # 3. Add any discovered headers that weren't caught by the main patterns
        # This is key for sections like "GraphRAG" or "Evaluation Results"
        for dh in discovered_headers:
            title_lower = dh["title"].lower()
            # If this title is substantially different from existing keys
            is_new = True
            for existing_key in list(sections.keys()):
                if title_lower in existing_key.lower() or existing_key.lower() in title_lower:
                    is_new = False
                    break
            if is_new:
                sections[dh["title"]] = dh["content"]

        # 4. Pseudo-Abstract Detection: If "Abstract" is missing, find it before the first detected header
        if "Abstract" not in sections:
            first_header_pos = len(text)
            # Find the earliest header position (predefined patterns)
            for section_name in self.SECTION_PATTERNS:
                pattern = rf"(?:\n|^)\s*(?:\d+\.?\s*)?{re.escape(section_name)}\s*(?:\n|$)"
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match and match.start() < first_header_pos:
                    first_header_pos = match.start()
            
            # Find earliest discovered header
            for dh in discovered_headers:
                if dh["start"] < first_header_pos:
                    first_header_pos = dh["start"]
            
            # Extract text before the first header (limited to first 4k chars to avoid taking the whole paper)
            pre_text = text[:first_header_pos].split('\n')
            # Look for a significant block (skip title/authors if they are likely at the start)
            # Find index where lines become long (paragraphs)
            abstract_lines = []
            found_block = False
            for line in pre_text:
                line = line.strip()
                if not line: continue
                if len(line) > 60: # Threshold for a sentence/paragraph line
                    found_block = True
                if found_block:
                    abstract_lines.append(line)
            
            if abstract_lines:
                sections["Abstract"] = "\n".join(abstract_lines[:30]) # Limit to ~30 lines
        
        return sections

    def process_pdf(self, pdf_path: Union[Path, str], paper_id: str) -> dict[str, Any]:
        """
        Extract text, detect sections.
        
        Args:
            pdf_path: Path to the PDF file.
            paper_id: Unique identifier for the paper.

        Returns:
            Dict with keys: paper_id, full_text, sections.
        """
        path = Path(pdf_path)
        full_text = self.extract_text(path)
        sections = self.detect_sections(full_text)

        result = {
            "paper_id": paper_id,
            "full_text": full_text,
            "sections": sections,
        }
        return result
