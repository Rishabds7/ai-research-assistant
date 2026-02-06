"""
PDF PROCESSING SERVICE
Project: Research Assistant
File: backend/services/pdf_processor.py

This service is the 'engine' for initial data extraction.
It uses PyMuPDF (fitz) to:
1. Load PDF files from disk.
2. Extract clean text from pages (handling multi-column layouts).
3. Use Regex and heuristics to detect the structural components (Abstract, Intro, Methods, etc.).
"""

import json
import re
from pathlib import Path
from typing import Any, Union

import fitz

class PDFProcessor:
    """
    Handles lower-level PDF manipulation and pattern matching.
    """

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
        "methods",
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
        "experimental setups",
        "experimental design",
        "evaluation",
        "evaluation results",
        "datasets",
        "datasets and metrics",
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
                # Use sort=True to better handle multi-column layouts
                text_parts.append(page.get_text("text", sort=True))
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
        Segment the paper into logical parts (Abstract, Methodology, etc.) using a two-pass approach.
        
        Pass 1: Identifies numbered headers (e.g., '1. Introduction', 'II. Methods').
        Pass 2: Searches for key academic keywords in isolation to catch non-numbered headers.
        """
        sections: dict[str, str] = {}
        text_lower = text.lower()
        
        # Pass 1: Generic Numbered Headers
        generic_header_pat = r"(?:\n|^)((?:\d+\.)*\d+\.?\s+([A-Z][A-Za-z\s]{3,60}))\s*(?:\n|$)"
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

        # Pass 2: Keyword-based matching for standard academic sections
        for section_name in self.SECTION_PATTERNS:
            # IMPROVED REGEX: Matches "Abstract:", "Abstract.", "1. Abstract" 
            # and crucially stops matching BEFORE the content starts, so inline content isn't lost.
            # \b ensures we don't match "AbstractVector"
            pattern = rf"(?:\n|^)\s*(?:\d+\.?\s*)?{re.escape(section_name)}\b[:.]?\s*"
            match = re.search(pattern, text_lower, re.IGNORECASE)
            
            if match:
                start = match.end()
                next_start = len(text)
                
                # Look ahead for the next major keyword boundary
                for other in self.SECTION_PATTERNS:
                    if other == section_name: continue
                    p = rf"\n\s*(?:\d+\.?\s*)?{re.escape(other)}\b[:.]?\s*"
                    m = re.search(p, text_lower[start:], re.IGNORECASE)
                    if m:
                        cand = start + m.start()
                        if cand < next_start: next_start = cand
                
                # Also check if a numbered header appears before the next keyword
                for dh in discovered_headers:
                    if dh["start"] > match.start() and dh["start"] < next_start:
                        next_start = dh["start"]
                
                content = text[start:next_start].strip()
                if content:
                    sections[section_name.title()] = content

        # Pass 3: Integration of unique discovered headers
        for dh in discovered_headers:
            title_lower = dh["title"].lower()
            is_new = True
            for existing_key in list(sections.keys()):
                if title_lower in existing_key.lower() or existing_key.lower() in title_lower:
                    is_new = False
                    break
            if is_new:
                sections[dh["title"]] = dh["content"]

        # Pass 4: Fallback for Abstract (Smart Identification)
        if "Abstract" not in sections:
            # Strategy: The abstract is usually the first significant block of text 
            # before the "Introduction".
            
            # Find where the next section starts (usually Introduction)
            end_pos = len(text)
            for existing_key, existing_content in sections.items():
                if "intro" in existing_key.lower():
                    pos = text.find(existing_content)
                    if pos != -1 and pos < end_pos:
                        end_pos = pos
                        break
            
            # If no Introduction found, just take the first 4000 chars
            if end_pos == len(text):
                end_pos = min(len(text), 4000)
            
            candidate_text = text[:end_pos].strip()
            
            # Filter out metadata lines (emails, affiliations, dates) to find the "meat"
            lines = candidate_text.split('\n')
            abstract_lines = []
            capture = False
            
            for line in lines:
                line = line.strip()
                if len(line) < 4: continue
                
                # Heuristic: Abstract paragraphs usually don't have special chars or look like emails
                if "@" in line or "University" in line or "IEEE" in line or "doi:" in line:
                    continue
                    
                # Once we hit a nice long paragraph, assume it's the abstract
                if len(line) > 100: 
                    capture = True
                
                # Or if it explicitly starts with "Abstract" (but wasn't caught by regex due to formatting)
                if line.lower().startswith("abstract"):
                    capture = True
                    line = line[8:].strip(" .:") # Remove the word "Abstract"
                
                if capture:
                    abstract_lines.append(line)
            
            # If we found nothing good, just take the raw first chunk
            if not abstract_lines:
                # Last resort: Take the middle 50% of the pre-intro text, assuming top is title/authors
                mid = len(lines) // 3
                abstract_lines = lines[mid:]
            
            final_abstract = "\n".join(abstract_lines)
            
            if final_abstract:
                sections["Abstract"] = final_abstract[:5000] # Cap it
        
        return sections

    def process_pdf(self, pdf_path: Union[Path, str], paper_id: str) -> dict[str, Any]:
        """
        Orchestrates the extraction pipeline: text -> logical segmentation.
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
