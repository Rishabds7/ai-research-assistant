"""
LLM ORCHESTRATION SERVICE
Project: Research Assistant
File: backend/services/llm_service.py

This is the Brain of the application. It maps high-level research questions 
(e.g., 'Summarize this') to specific LLM prompts.

AI INTERVIEW FOCUS:
1. Factory Pattern: We use a custom 'LLMService' class that acts as a factory. 
   It dynamically instantiates either GeminiLLMService (Google Cloud) or 
   OllamaLLMService (Local Llama 3) based on environment settings.
2. Prompt Engineering: Study the 'extract_methodology' and 'smart_summarize_paper' 
   prompts. We use 'Few-Shot' prompting and 'Chain-of-Thought' style instructions 
   to ensure the LLM returns valid JSON.
3. Post-Processing: We don't trust the raw LLM output. The 'clean_llm_summary' 
   function uses Regex to strip out 'AI chatter' and meta-talk, ensuring a 
   professional UI.
"""

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Protocol, Union

logger = logging.getLogger(__name__)

import google.generativeai as genai
import requests
from google.api_core import exceptions as google_exceptions

from django.conf import settings

# Global configurations loaded from Django settings.
# These determine whether we use a remote API (Gemini) or a local host (Ollama).
GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_MODEL = settings.GEMINI_MODEL
LLM_PROVIDER = settings.LLM_PROVIDER
OLLAMA_HOST = settings.OLLAMA_HOST
OLLAMA_MODEL = settings.OLLAMA_MODEL


class LLMBackend(Protocol):
    """
    Defining a Protocol (Interface) for AI providers.
    Every provider (Gemini or Ollama) must implement these research tasks.
    """
    def extract_methodology(self, context: str) -> Dict[str, Any]: ...
    def summarize_sections(self, sections: Dict[str, str], full_text: str = "") -> Dict[str, str]: ...
    def extract_datasets(self, context: str) -> List[str]: ...
    def extract_licenses(self, paper_text: str) -> List[str]: ...
    def extract_paper_info(self, context: str) -> Dict[str, str]: ...
    def generate_global_summary(self, section_summaries: Dict[str, str]) -> str: ...
    def analyze_research_gaps(self, paper_contexts: List[Dict[str, str]]) -> str: ...


def _strip_json_markdown(raw: str) -> str:
    """
    CLEANING LOGIC:
    Many LLMs (like Llama 3) wrap their answers in ```json blocks even when asked not to.
    This function strips those markers to ensure the JSON parser targets only the raw data.
    
    Args:
        raw: The raw string response from the LLM.
        
    Returns:
        str: The string with markdown code blocks removed.
    """
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _parse_json_safe(raw: str, default: Any = None) -> Any:
    """
    ROBUST PARSING LOGIC (SELF-CORRECTION):
    Standard json.loads() fails if the LLM includes preamble ("Here is your JSON:") 
    or postamble ("Hope this helps!").
    
    Workflow:
    1. Try parsing directly.
    2. If fails, use Regex to find the first '{' and last '}' or '[' and ']'.
    3. Extract that middle 'core' and try parsing again.
    
    Args:
        raw: The raw output string from the LLM.
        default: Value to return if parsing fails completely.
        
    Returns:
        Any: The parsed JSON object (dict or list) or the default value.
    """
    if not raw:
        return default if default is not None else []
    
    cleaned = _strip_json_markdown(raw)
    
    try:
        # Attempt direct parse first
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # Try to find JSON object or list in text if mixed with chatter
        try:
            # Use multi-line regex to capture the largest JSON block in the response
            dict_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            list_match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
            
            parsed = None
            if dict_match and list_match:
                # Prioritize whichever comes first in the text
                if dict_match.start() < list_match.start():
                    parsed = json.loads(dict_match.group(1))
                else:
                    parsed = json.loads(list_match.group(1))
            elif dict_match:
                parsed = json.loads(dict_match.group(1))
            elif list_match:
                parsed = json.loads(list_match.group(1))
            
            if parsed is not None:
                # Consistency Layer: standardize wrapping of returned lists
                if isinstance(parsed, dict):
                    for key in ["datasets", "items", "data", "results"]:
                        if key in parsed and isinstance(parsed[key], list):
                            return parsed[key]
                return parsed
        except Exception:
            pass

        if default is not None:
            return default
        raise ValueError(f"Failed to parse JSON despite recovery: {e}") from e


def clean_llm_summary(text: str) -> str:
    """
    Aggressively removes intro/outro meta-text from the LLM. 
    Also normalizes content by merging wrapped lines and removing leading bullets.
    
    Args:
        text: Raw summary text from LLM.
        
    Returns:
        str: Cleaned, bulleted text.
    """
    if not text:
        return ""
        
    lines = text.split('\n')
    processed_points = []
    
    # Phrases usually added by LLMs that aren't part of the content
    meta_patterns = [
        r"^here (is|are) (the )?\d* (summary|bullet points?|key points?|points?)",
        r"^(i('ve| have))? (summarized?|prepared|created|extracted)",
        r"^based on (the |these )?",
        r"^the (section|text|paper|following) (discusses?|presents?|describes?|contains?|outlines?|provides?)",
        r"^this (section|document|paper|text) (discusses?|presents?|describes?|contains?|provides?)",
        r"^in (this|the) section",
        r"^summary of (the )?",
        r"^bullet points?:",
        r"^key (points?|findings?):",
        r"^key findings?:",
        r"provide only the bullet points",
        r"^as requested",
        r"^following (is|are)",
        r"^below (is|are)",
        r"^sure, here",
        r"^i have extracted",
        r"^certainly",
        r"^(here|below) is the list",
        r"^(the|following) bullet points? outline",
        r"^in summary",
        r"^overall,"
    ]
    
    # Pre-clean the list: merge lines that clearly look like continuations of the same point
    merged_lines = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned: continue
        
        # Strip bullets from this specific line for checking
        content = re.sub(r"^[ \t]*([•\-*–—\d\.]+[ \t]*)+", "", cleaned).strip()
        if not content: continue
        
        if merged_lines:
            last = merged_lines[-1]
            # If last ends with a hyphen or NO punctuation, and current starts with lowercase or is short
            # Logic: If it looks like a break
            if (last.endswith('-') or not re.search(r'[.!?]$', last)) and (content[0].islower() or len(content) < 40):
                if last.endswith('-'):
                    merged_lines[-1] = last[:-1] + content
                else:
                    merged_lines[-1] = last + " " + content
                continue
        
        merged_lines.append(cleaned)
    
    for line in merged_lines:
        cleaned_line = line.strip()
        
        # Skip empty lines
        if not cleaned_line:
            continue
            
        # Check if line is meta-text
        is_meta = False
        stripped_lower = cleaned_line.lower()
        for pattern in meta_patterns:
            if re.search(pattern, stripped_lower):
                is_meta = True
                break
        
        if is_meta:
            continue

        # STRIP LEADING BULLETS/NUMBERS (keeping only the content)
        content = re.sub(r"^[ \t]*([•\-*–—\d\.]+[ \t]*)+", "", cleaned_line).strip()
        if not content:
            continue

        processed_points.append(content)
            
    return '\n'.join(processed_points)


def _extract_license_snippets(text: str) -> List[str]:
    """
    Heuristic snippet finder to locate license/copyright info across the WHOLE paper.
    Returns a list of relevant text chunks with context.
    
    Args:
        text: Full text of the paper.
        
    Returns:
        List[str]: List of relevant text snippets.
    """
    # Strong License Keywords (High signal)
    strong_keywords = [
        r"creative commons", r"creativecommons\.org", r"CC[- ]?BY", r"CC[- ]?0", r"CC[- ]?SA", r"CC[- ]?NC",
        r"MIT license", r"Apache 2", r"GNU", r"GPL", r"BSD", r"Public Domain", r"CC BY",
        r"proprietary", r"all rights reserved", r"©", r"copyright"
    ]
    
    # Potential Context Keywords (Lower signal, need near stronger words)
    context_keywords = [
        r"licensed? under", r"permission", r"reproduced from", r"adapted from",
        r"figure caption", r"fig\.", r"caption", r"acknowledgments",
        r"terms of use", r"code availability", r"data availability",
        r"github\.com", r"available at", r"source code", r"repository",
        r"non-commercial", r"commercial use", r"academic use", r"restricted use",
        r"usage terms", r"terms of service", r"redistribution", r"citation policy"
    ]
    
    all_keywords = strong_keywords + context_keywords
    combined_pattern = "|".join(all_keywords)
    matches = list(re.finditer(combined_pattern, text, re.IGNORECASE))
    
    head_text = text[:8000].replace('\n', ' ')
    tail_text = text[-8000:].replace('\n', ' ')
    
    # Always include the head and tail of the paper
    snippets = [
        f"[HEAD] {head_text}",
        f"[TAIL] {tail_text}"
    ]
    
    # Strategic Section Search
    structure_keywords = ["acknowledgments", "appendix", "data availability", "code availability", "software availability"]
    for sk in structure_keywords:
        m = re.search(rf"\b{sk}\b", text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - 500)
            end = min(len(text), m.end() + 3000)
            section_text = text[start:end].replace('\n', ' ')
            snippets.append(f"[SECTION: {sk.upper()}] {section_text}")

    if not matches:
        return snippets[:40]
        
    CONTEXT_SIZE = 1500 # Even larger context
    
    ranges = []
    for m in matches:
        # Prioritize matches that are likely to be headers or captions
        is_strong = any(re.search(sk, m.group(0), re.IGNORECASE) for sk in strong_keywords)
        
        # If it's a weak match like "figure", only include if it's near another keyword
        # or just include it with a wider window to be safe.
        start = max(0, m.start() - CONTEXT_SIZE)
        end = min(len(text), m.end() + CONTEXT_SIZE)
        ranges.append((start, end))
        
    ranges.sort()
    merged = []
    if ranges:
        curr_start, curr_end = ranges[0]
        for start, end in ranges[1:]:
            if start < curr_end:
                curr_end = max(curr_end, end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = start, end
        merged.append((curr_start, curr_end))
    
    for start, end in merged:
        snippet = text[start:end].replace("\n", " ").strip()
        # Deduplication check
        if not any(snippet[:100] in s for s in snippets):
            snippets.append(snippet)
        
    return snippets[:100] # Increase limit to 100 to ensure "whole paper" is covered


def _extract_dataset_snippets(text: str) -> List[str]:
    """
    Heuristic snippet finder to locate dataset/source info across the WHOLE paper.
    
    Args:
        text: Full text.
        
    Returns:
        List[str]: Relevant snippets.
    """
    keywords = [
        r"dataset", r"benchmark", r"corpus", r"evaluation set",
        r"ImageNet", r"COCO", r"MNIST", r"CIFAR", r"SQuAD", r"GLUE",
        r"MIMIC", r"ChestX-ray", r"Common Crawl", r"Wikipedia",
        r"data availability", r"we use the", r"downloaded from",
        r"available at", r"podcasts?", r"newsletters?",
        r"experimental setup", r"data collection"
    ]
    combined_pattern = "|".join(keywords)
    matches = list(re.finditer(combined_pattern, text, re.IGNORECASE))
    
    if not matches:
        return []
        
    snippets = []
    CONTEXT_SIZE = 800
    
    ranges = []
    for m in matches:
        start = max(0, m.start() - CONTEXT_SIZE)
        end = min(len(text), m.end() + CONTEXT_SIZE)
        ranges.append((start, end))
        
    ranges.sort()
    merged = []
    if ranges:
        curr_start, curr_end = ranges[0]
        for start, end in ranges[1:]:
            if start < curr_end:
                curr_end = max(curr_end, end)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = start, end
        merged.append((curr_start, curr_end))
    
    for start, end in merged:
        snippet = text[start:end].replace("\n", " ").strip()
        snippets.append(snippet)
        
    return snippets[:25]


class GeminiLLMService:
    """
    Implementation for Google Gemini Pro.
    Leverages huge context windows (1M+ tokens) and high-level reasoning.
    """
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            logger.error("CRITICAL: GEMINI_API_KEY is missing! Check your environment variables.")
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={"temperature": 0.1}
        )
        logger.info(f"LLM: Initialized Gemini service with model {GEMINI_MODEL}")

    def _generate(self, prompt: str) -> str:
        """
        Low-level API call wrapper with exponential backoff for 429 errors.
        
        Args:
            prompt: The full prompt string.
            
        Returns:
            str: The LLM's text response.
        """
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries + 1):
            try:
                response = self.model.generate_content(prompt)
                if response.candidates and response.candidates[0].content.parts:
                    return response.text
                return ""
            except Exception as e:
                # Check for 429 Resource Exhausted (Google API or gRPC error)
                error_str = str(e)
                is_429 = "429" in error_str or "Resource exhausted" in error_str
                
                if is_429 and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Gemini 429 Rate Limit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                    continue
                
                logger.error(f"Gemini error: {e}")
                return ""

    def extract_paper_info(self, context: str) -> Dict[str, str]:
        """
        Uses first 10,000 characters to extract Title and Authors.
        Academic titles are usually prominent in the first few lines of raw text.
        
        Args:
            context: Text context (usually preamble of paper).
            
        Returns:
            Dict: with keys 'title', 'authors', 'year', 'journal'.
        """
        prompt = """Extract the following metadata from this research paper:
1. Title
2. Authors
3. Publication Year (if mentioned, otherwise "Unknown")
4. Journal or Conference Name (if mentioned, otherwise "Unknown")

Return ONLY a JSON object with this exact structure:
{
    "title": "Full paper title",
    "authors": ["Author One", "Author Two"],
    "year": "2024",
    "journal": "Nature / ArXiv / etc."
}

Text:
""" + context[:12000]
        raw = self._generate(prompt)
        return _parse_json_safe(raw, {
            "title": "Unknown", 
            "authors": ["Unknown"], 
            "year": "Unknown", 
            "journal": "Unknown"
        })

    def extract_datasets(self, context: str) -> List[str]:
        """
        Uses snippet-based isolation to find data sources. 
        Better than full-text extraction for long documents as it avoids dilution.
        
        Args:
            context: Combined text snippets containing dataset keywords.
            
        Returns:
            List[str]: List of dataset names.
        """
        snippets = _extract_dataset_snippets(context)
        snippets_text = "\n---\n".join(snippets)
        # LLM Call for identification
        prompt = """Extract ALL specific data sources and datasets mentioned in these snippets from a research paper.

Look for:
- Standard Benchmarks (ImageNet, SQuAD, etc.)
- Named local/custom datasets
- Alternative sources like specific podcasts, newsletters, or web sources.

Rules:
1. Return ONLY a JSON array of specific names: ["Name1", "Name2", ...]
2. Be specific (e.g., "ImageNet-1k" not just "ImageNet").
3. Include names of podcasts/newsletters if explicitly mentioned.
4. If NO specific sources or datasets are found, return ["None mentioned"].
5. Deduplicate and normalize names.

Snippets:
""" + snippets_text
        raw = self._generate(prompt)
        result = _parse_json_safe(raw, ["None mentioned"])
        return result if result else ["None mentioned"]
    
    def analyze_research_gaps(self, paper_contexts: List[Dict[str, str]]) -> str:
        """Identical to Gemini implementation - delegates to Ollama."""
        if not paper_contexts or len(paper_contexts) < 2:
            return "Need at least 2 papers for meaningful gap analysis."
        
        papers_summary = []
        for i, ctx in enumerate(paper_contexts, 1):
            title = ctx.get('title', f'Paper {i}')
            future_work = ctx.get('future_work', '')
            conclusion = ctx.get('conclusion', '')
            limitations = ctx.get('limitations', '')
            
            paper_text = f"**Paper {i}: {title}**\n"
            if conclusion:
                paper_text += f"Conclusion: {conclusion[:1500]}\n"
            if future_work:
                paper_text += f"Future Work: {future_work[:1500]}\n"
            if limitations:
                paper_text += f"Limitations: {limitations[:1000]}\n"
            
            papers_summary.append(paper_text)
        
        # Python doesn't allow backslashes in f-string expressions, extract separator
        separator = '\n\n---\n\n'
        papers_text = separator.join(papers_summary)
        
        prompt = f"""You are a research analyst identifying gaps across multiple academic papers.

**Your Task:**
Analyze the following papers and provide:
1. **Common Themes**: What research areas do these papers collectively address?
2. **Research Gaps**: What questions remain unanswered? What hasn't been explored?
3. **Future Directions**: What are the most promising next steps?

**Papers:**
{papers_text}

**Output Format** (Markdown with bullet points):
##  Common Themes
- [Theme 1]
- [Theme 2]

## Identified Research Gaps
- [Gap 1]
- [Gap 2]

## Suggested Future Directions
- [Direction 1]
- [Direction 2]

**Important:**
- If papers cover completely different domains, state: "Papers cover different research areas with minimal overlap."
- Focus on ACTIONABLE gaps (specific experiments, datasets, methods not yet tried)
- Be concise (3-5 points per section)
"""
        
        result = self._generate(prompt=prompt, temperature=0.4, max_tokens=2000)
        return clean_llm_summary(result) if result else "Failed to generate gap analysis."

    def extract_licenses(self, paper_text: str) -> List[str]:
        """
        Hyper-accurate license scanner.
        Combines targeted snippet extraction for high-signal areas 
        with full-text scanning for global context.
        
        Args:
            paper_text: Full text of the paper.
            
        Returns:
            List[str]: List of identified licenses.
        """
        # 1. Target the High-Signal areas first (Head, Tail, Acknowledgments)
        head = paper_text[:15000].replace('\n', ' ')
        tail = paper_text[-15000:].replace('\n', ' ')
        
        # Look for specific structural sections in the full text
        structural = ""
        for section in ["acknowledgments", "appendix", "data availability", "code availability", "software availability"]:
            match = re.search(rf"\b{section}\b", paper_text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 1000)
                end = min(len(paper_text), match.end() + 5000)
                structural += f"\n[SECTION: {section.upper()}]\n{paper_text[start:end]}\n"

        # 2. Prepare the Global Context (Capped to 150k for speed/cost)
        global_context = paper_text[:150000]
        
        prompt = """You are a professional license auditor. Analyze the paper text below and identify ALL software, data, or content licenses.

Rules:
1. Return ONLY a JSON LIST of strings: ["MIT License", "CC BY 4.0", ...]
2. ONLY include actual LEGAL LICENSES. 
3. DO NOT include software frameworks or libraries (e.g., "TensorFlow", "PyTorch", "JAX", "NumPy")—these are NOT licenses.
4. If NO valid licenses are found, return ["None mentioned"].
5. Standardize names using the list of common licenses below as a reference.

POSSIBLE LICENSES TO IDENTIFY:
- Creative Commons: CC BY, CC BY-SA, CC BY-ND, CC BY-NC, CC BY-NC-SA, CC BY-NC-ND, CC0
- Software: MIT License, Apache License 2.0, BSD 2-Clause, BSD 3-Clause, ISC License, Boost Software License 1.0, zlib License
- GNU: GPL-2.0, GPL-3.0, LGPL-2.1, LGPL-3.0, AGPL-3.0
- Other: Mozilla Public License 2.0 (MPL-2.0), Eclipse Public License 2.0 (EPL-2.0), CDDL-1.0
- Database/Data: Open Database License (ODbL), ODC-By, PDDL, Public Domain Mark
- AI/ML Specific: CreativeML OpenRAIL-M, BigScience OpenRAIL-M, OpenRAIL-M
- Research Terms: "available for non-commercial research", "restricted use", "citation required"

Paper Context for Deep Audit:
---
[BEGINNING]
""" + head + """

[STRUCTURAL SECTIONS]
""" + structural + """

[END OF DOCUMENT]
""" + tail + """

[FULL PAPER SCAN (Truncated for performance)]
""" + global_context + """
---

Return ONLY the JSON list of strings."""

        raw = self._generate(prompt)
        items = _parse_json_safe(raw, ["None mentioned"])
        
        # Clean results
        cleaned = []
        seen = set()
        for i in items:
            if not isinstance(i, str): continue
            val = i.strip().strip('"').strip("'")
            if val and val.lower() not in seen:
                cleaned.append(val)
                seen.add(val.lower())
        
        # If we got junk or empty after cleaning
        if not cleaned: return ["None mentioned"]
        
        # If "None mentioned" is one of many, remove it
        if len(cleaned) > 1 and "None mentioned" in cleaned:
            cleaned = [c for c in cleaned if c != "None mentioned"]
            
        return cleaned

    def _pre_clean_content(self, text: str) -> str:
        """
        Fixes PDF extraction artifacts like mid-word hyphens and unnecessary line breaks
        before sending to the LLM.
        
        Args:
            text: Raw input text.
            
        Returns:
            str: Cleaned text.
        """
        if not text: return ""
        # 1. Join words broken by hyphens at end of lines
        text = re.sub(r'(\w)-\n\s*(\w)', r'\1\2', text)
        # 2. Join lines that don't end in punctuation
        lines = text.split('\n')
        processed = []
        for line in lines:
            line = line.strip()
            if not line: continue
            if processed and not re.search(r'[.!?]$', processed[-1]):
                processed[-1] = processed[-1] + " " + line
            else:
                processed.append(line)
        return "\n".join(processed)

    def summarize_sections(self, sections: Dict[str, str], full_text: str = "") -> Dict[str, str]:
        """
        Maps paper sections to standardized academic sections and creates summaries.
        Uses full_text as a fallback if specific sections like Abstract are missing.
        
        Args:
            sections: Dictionary of {SectionName: Content}.
            full_text: The entire paper text (as backup).
            
        Returns:
            Dict: Map of {StandardSectionName: Summary}.
        """
        # Standardized section mapping
        STANDARD_SECTIONS = [
            'Abstract',
            'Introduction', 
            'Background',
            'Methodology',
            'Experiments',
            'Results',
            'Conclusion'
        ]
        
        # Section mapping keywords
        SECTION_MAPPING = {
            'Abstract': ['abstract', 'abstract.'],
            'Introduction': ['introduction', 'intro', 'motivation', 'problem statement'],
            'Background': ['background', 'related work', 'literature review', 'prior work', 'preliminaries', 'context', 'motivation'],
            'Methodology': ['methodology', 'method', 'approach', 'model', 'architecture', 'framework', 'technique', 'algorithm', 'system design'],
            'Experiments': ['experiment', 'evaluation', 'setup', 'implementation', 'analysis', 'empirical'],
            'Results': ['result', 'finding', 'performance', 'discussion', 'observation', 'comparison'],
            'Conclusion': ['conclusion', 'concluding', 'future work', 'limitation', 'summary']
        }
        
        # Map paper sections to standard sections
        mapped_sections = {}
        for standard_section in STANDARD_SECTIONS:
            mapped_content = []
            keywords = SECTION_MAPPING[standard_section]
            
            for section_name, content in sections.items():
                section_lower = section_name.lower()
                if any(keyword in section_lower for keyword in keywords):
                    mapped_content.append(content)
            
            if mapped_content:
                mapped_sections[standard_section] = '\n\n'.join(mapped_content)
        
        # SMART FALLBACKS: Ensure no section is left entirely empty if full_text is available
        if full_text:
            if not mapped_sections.get('Abstract') or len(mapped_sections['Abstract']) < 100:
                mapped_sections['Abstract'] = full_text[:8000]

            if not mapped_sections.get('Introduction') or len(mapped_sections['Introduction']) < 100:
                mapped_sections['Introduction'] = full_text[2000:15000]

            if not mapped_sections.get('Background') or len(mapped_sections['Background']) < 100:
                # Background usually follows intro
                start = int(len(full_text) * 0.1)
                end = int(len(full_text) * 0.3)
                mapped_sections['Background'] = full_text[start:end]

            if not mapped_sections.get('Methodology') or len(mapped_sections['Methodology']) < 100:
                start = int(len(full_text) * 0.25)
                end = int(len(full_text) * 0.55)
                mapped_sections['Methodology'] = full_text[start:end]

            if not mapped_sections.get('Experiments') or len(mapped_sections['Experiments']) < 100:
                start = int(len(full_text) * 0.45)
                end = int(len(full_text) * 0.75)
                mapped_sections['Experiments'] = full_text[start:end]

            if not mapped_sections.get('Results') or len(mapped_sections['Results']) < 100:
                start = int(len(full_text) * 0.65)
                end = int(len(full_text) * 0.9)
                mapped_sections['Results'] = full_text[start:end]

            if not mapped_sections.get('Conclusion') or len(mapped_sections['Conclusion']) < 100:
                mapped_sections['Conclusion'] = full_text[-12000:]
        
        # Generate summaries for each standard section
        summaries = {}
        # Iterate through STANDARD_SECTIONS to maintain order and ensure we check all
        for section_name in STANDARD_SECTIONS:
            content = mapped_sections.get(section_name)
            if not content or len(content.strip()) < 50:
                continue
                
            prompt = f"""You are a senior research scientist. Provide a high-density, technical executive summary of the "{section_name}" section from a research paper.

CONSTRAINTS:
1. Provide exactly 6-8 comprehensive bullet points. 
2. Each point MUST start with a '-' symbol.
3. Each point MUST be a complete, self-contained technical insight (do not split one sentence into two points).
4. Each point MUST be a single, long-form continuous line.
5. NO introductory text, NO meta-commentary.
6. MANDATORY: Fix any broken words or line-breaks from the source text. 

Content to summarize:
{self._pre_clean_content(content)[:15000]}"""
            
            raw_summary = self._generate(prompt)
            summaries[section_name] = clean_llm_summary(raw_summary)
            
            # Rate limiting: Sleep briefly to avoid hitting Gemini's RPM/TPM limits quickly
            time.sleep(1)
        
        return summaries

    def extract_methodology(self, context: str) -> Dict[str, Any]:
        """
        Highly structured methodology extraction.
        Returns a JSON schema containing datasets, model architecture, and metrics.
        
        Args:
            context: Text context focused on methods.
        
        Returns:
            Dict: Schema with keys 'datasets', 'model', 'metrics', 'results', 'summary'.
        """
        prompt = f"Extract methodology details (datasets, model, metrics, results, summary). Return ONLY JSON.\n\nText:\n{context}"
        raw = self._generate(prompt)
        return _parse_json_safe(raw, {})

    def generate_global_summary(self, section_summaries: Dict[str, str]) -> str:
        """
        Final synthesis step. Combines individual section insights into 
        a 'Global Summary' (TL;DR) for the reviewer dashboard.
        
        Args:
            section_summaries: Map of section names to summary texts.
            
        Returns:
            str: Global summary text.
        """
        combined = "\n".join([f"{n}:\n{t}" for n, t in section_summaries.items()])
        prompt = f"""Synthesize these section summaries into a comprehensive final overview of the paper.

REQUIREMENTS:
1. Provide 5-8 powerful, high-impact bullet points.
2. Each bullet point MUST be a single continuous line. DO NOT use hard line breaks or wrap text.
3. DO NOT include any introductory or meta text.
4. Provide ONLY the points, one per line. No symbols or leading numbers.

Summaries:
{combined}"""
        return clean_llm_summary(self._generate(prompt))


class OllamaLLMService:
    """
    LOCAL AI IMPLEMENTATION.
    Connects to a local Ollama server. 
    Crucial for interview discussions about privacy and offline research tools.
    """
    def __init__(self) -> None:
        if OLLAMA_HOST:
             self.host = OLLAMA_HOST.rstrip("/")
        else:
             self.host = "http://localhost:11434"
        self.model = OLLAMA_MODEL
        logger.info(f"LLM: Initialized Ollama service at {self.host} with model {self.model}")

    def _generate(self, prompt: str, system: str = "") -> str:
        """
        Standard HTTP POST to the Ollama /api/generate endpoint.
        
        Args:
            prompt: User prompt.
            system: System prompt (optional).
            
        Returns:
            str: Generated text.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.1, 
                "num_ctx": 16384  # Increased for research papers
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            return resp.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return ""

    # Complete implementation matching GeminiLLMService
    def extract_paper_info(self, context: str) -> Dict[str, str]:
        """
        Extracts title and authors from the paper context.
        
        Args:
            context: Text context (usually preamble of paper).
            
        Returns:
            Dict: with keys 'title', 'authors' (plus optional keys).
        """
        prompt = f"""Analyze the provided text to identify its document type, title, and authors.
        
        Task 1: Classify the document. Is it a "Research Paper" (academic, technical, scientific)?
        If NO (e.g., news article, bank statement, novel, slide deck):
          - Set "title" to: "NON-RESEARCH: [Original Title]"
          - Set "authors" to: ["N/A"]
        
        Task 2: If YES, extract the full title and author list.
        
        Return ONLY a JSON object:
        {{
            "title": "Title String",
            "authors": ["Author 1", "Author 2"]
        }}
        
        If info is found but ambiguous, make your best guess.
        
        Text Snippet:
        {context[:5000]}"""
        return _parse_json_safe(self._generate(prompt), {"title": "Unknown", "authors": ["Unknown"]})
    
    def extract_datasets(self, context: str) -> List[str]:
        """
        Extracts dataset names from text snippets.
        
        Args:
            context: Text snippets containing keywords.
            
        Returns:
            List[str]: List of dataset names.
        """
        snippets = _extract_dataset_snippets(context)
        if not snippets: return []
        
        snippets_text = "\n---\n".join(snippets)
        prompt = f"""Extract ALL specific data sources and datasets from these paper snippets.
Return ONLY a JSON array of exact names: ["Name1", "Name2", ...]
If none found, return [].

Snippets:
{snippets_text}"""
        raw = self._generate(prompt)
        return _parse_json_safe(raw, [])
    
    def extract_licenses(self, paper_text: str) -> List[str]:
        """
        Extracts licenses from the full paper text.
        
        Args:
            paper_text: Full text of the paper.
            
        Returns:
            List[str]: List of identified licenses.
        """
        # 1. Scan full text for license snippets
        snippets = _extract_license_snippets(paper_text)
        if not snippets: return []
            
        # 2. LLM Call with evidence extraction
        snippets_text = "\n---\n".join(snippets)
        prompt = f"""Analyze these snippets and identify exact licenses (MIT, Apache, CC, etc.).
Return a JSON LIST of objects: [{{"license": "Name", "evidence": "Quote"}}]
Return ONLY JSON.

Snippets:
{snippets_text}"""
        raw = self._generate(prompt)
        items = _parse_json_safe(raw, [])
        
        licenses = []
        seen = set()
        for item in items:
            if isinstance(item, dict) and 'license' in item:
                lic = item['license'].strip()
                if lic and lic.lower() not in seen:
                    licenses.append(lic)
                    seen.add(lic.lower())
        return licenses

    def analyze_research_gaps(self, paper_contexts: List[Dict[str, str]]) -> str:
        """
        MAP-REDUCE RESEARCH GAP ANALYSIS.
        Analyzes multiple papers to identify unexplored research areas.
        
        This method implements a multi-document synthesis pattern:
        - Map: Extract conclusions/future work from each paper
        - Reduce: Synthesize common gaps and opportunities
        
        Args:
            paper_contexts: List of dicts with keys:
                - 'title': Paper title
                - 'future_work': Future work section text
                - 'conclusion': Conclusion section text
                - 'limitations': Limitations section text (optional)
        
        Returns:
            str: Markdown-formatted gap analysis with:
                - Common themes across papers
                - Identified research gaps
                - Suggested future directions
        """
        if not paper_contexts or len(paper_contexts) < 2:
            return "Need at least 2 papers for meaningful gap analysis."
        
        # Build context from all papers (Map phase)
        papers_summary = []
        for i, ctx in enumerate(paper_contexts, 1):
            title = ctx.get('title', f'Paper {i}')
            future_work = ctx.get('future_work', '')
            conclusion = ctx.get('conclusion', '')
            limitations = ctx.get('limitations', '')
            
            paper_text = f"**Paper {i}: {title}**\n"
            if conclusion:
                paper_text += f"Conclusion: {conclusion[:1500]}\n"
            if future_work:
                paper_text += f"Future Work: {future_work[:1500]}\n"
            if limitations:
                paper_text += f"Limitations: {limitations[:1000]}\n"
            
            papers_summary.append(paper_text)
        
        # Python doesn't allow backslashes in f-string expressions, extract separator
        separator = '\n\n---\n\n'
        papers_text = separator.join(papers_summary)
        
        # Reduce phase: LLM synthesizes gaps
        prompt = f"""You are a research analyst identifying gaps across multiple academic papers.

**Your Task:**
Analyze the following papers and provide:
1. **Common Themes**: What research areas do these papers collectively address?
2. **Research Gaps**: What questions remain unanswered? What hasn't been explored?
3. **Future Directions**: What are the most promising next steps?

**Papers:**
{papers_text}

**Output Format** (Markdown with bullet points):
## Common Themes
- [Theme 1]
- [Theme 2]

## Identified Research Gaps
- [Gap 1]
- [Gap 2]

## Suggested Future Directions
- [Direction 1]
- [Direction 2]

**Important:**
- If papers cover completely different domains, state: "Papers cover different research areas with minimal overlap."
- Focus on ACTIONABLE gaps (specific experiments, datasets, methods not yet tried)
- Be concise (3-5 points per section)
"""
        
        result = self._generate(prompt=prompt, temperature=0.4, max_tokens=2000)
        return clean_llm_summary(result) if result else "Failed to generate gap analysis."

    def summarize_sections(self, sections: Dict[str, str], full_text: str = "") -> Dict[str, str]:
        """
        Maps paper sections to standardized academic sections and creates summaries.
        Returns summaries in a fixed order with bullet points.
        
        Args:
            sections: Dictionary of {SectionName: Content}.
            full_text: (Unused in Ollama impl, kept for Protocol compatibility).
            
        Returns:
            Dict: Map of {StandardSectionName: Summary}.
        """
        # Standardized section mapping
        STANDARD_SECTIONS = [
            'Abstract',
            'Introduction', 
            'Background',
            'Methodology',
            'Experiments',
            'Results',
            'Conclusion',
            'References'
        ]
        
        # Section mapping keywords
        SECTION_MAPPING = {
            'Abstract': ['abstract', 'summary'],
            'Introduction': ['introduction', 'intro', 'motivation'],
            'Background': ['background', 'related work', 'literature review', 'prior work'],
            'Methodology': ['methodology', 'method', 'approach', 'model', 'architecture', 'framework', 'technique', 'algorithm'],
            'Experiments': ['experiment', 'evaluation', 'setup', 'implementation', 'analysis'],
            'Results': ['result', 'finding', 'performance', 'discussion', 'observation'],
            'Conclusion': ['conclusion', 'future work', 'limitation', 'summary'],
            'References': ['reference', 'bibliography', 'citation']
        }
        
        # Map paper sections to standard sections
        mapped_sections = {}
        for standard_section in STANDARD_SECTIONS:
            mapped_content = []
            keywords = SECTION_MAPPING[standard_section]
            
            for section_name, content in sections.items():
                section_lower = section_name.lower()
                if any(keyword in section_lower for keyword in keywords):
                    mapped_content.append(content)
            
            if mapped_content:
                mapped_sections[standard_section] = '\n\n'.join(mapped_content)
        
        # Generate summaries for each standard section
        summaries = {}
        for section_name, content in mapped_sections.items():
            if section_name == 'References':
                continue
                
            prompt = f"""Summarize this {section_name} section from a research paper.

REQUIREMENTS:
1. Provide 6-8 descriptive bullet points.
2. Each bullet point MUST be a single continuous line. DO NOT use hard line breaks.
3. DO NOT include introductory text or bullet symbols (- or •).
4. Provide ONLY the points, one per line.

Section Content:
{content[:8000]}"""
            raw_summary = self._generate(prompt)
            summaries[section_name] = clean_llm_summary(raw_summary)
        
        return summaries
    
    def extract_methodology(self, context: str) -> Dict[str, Any]:
        """
        Extracts methodology details.
        
        Args:
            context: Text context.
            
        Returns:
            Dict: Schema with methodology details.
        """
        prompt = f"Extract methodology details (datasets, model, metrics, results, summary). Return ONLY JSON.\n\nText:\n{context[:6000]}"
        raw = self._generate(prompt)
        return _parse_json_safe(raw, {})

    def generate_global_summary(self, section_summaries: Dict[str, str]) -> str:
        """
        Generates a global summary from section summaries.
        
        Args:
            section_summaries: Map of section summaries.
            
        Returns:
            str: Global summary text.
        """
        combined = "\n".join([f"{n}:\n{t}" for n, t in section_summaries.items()])
        prompt = f"""Synthesize these summaries into a global overview of the paper with 6-8 high-impact points.

REQUIREMENTS:
1. Each bullet point MUST be a single continuous line. DO NOT use hard line breaks.
2. DO NOT include introductory text or bullet symbols.
3. Provide ONLY the points, one per line.

Summaries:
{combined}"""
        return clean_llm_summary(self._generate(prompt))


class LLMService:
    """
    Factory class for getting the configured LLM backend.
    
    This class implements the Singleton pattern to ensure only one instance 
    of the LLM service is created and reused throughout the application lifecycle.
    """
    _instance: Optional[Union[GeminiLLMService, OllamaLLMService]] = None

    def __new__(cls) -> Union[GeminiLLMService, OllamaLLMService]:
        """
        Creates or returns the singleton instance of the LLM service.
        
        Returns:
            Union[GeminiLLMService, OllamaLLMService]: The configured LLM service instance.
        """
        if cls._instance is None:
            if LLM_PROVIDER == "gemini":
                cls._instance = GeminiLLMService()
            else:
                cls._instance = OllamaLLMService()
        return cls._instance
