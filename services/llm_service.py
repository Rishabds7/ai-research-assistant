"""
LLM service: supports Google Gemini and Ollama.
"""

import json
import re
import time
from typing import Any, Optional, Protocol

import google.generativeai as genai
import requests
from google.api_core import exceptions as google_exceptions

from config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_MODEL,
)


class LLMBackend(Protocol):
    def extract_methodology(self, context: str) -> dict[str, Any]: ...
    def identify_gaps(self, methodologies_list: list[dict[str, Any]]) -> dict[str, Any]: ...
    def generate_comparison_table(self, methodologies_list: list[dict[str, Any]]) -> str: ...


def _strip_json_markdown(raw: str) -> str:
    """Remove ```json and ``` wrappers from LLM response before parsing."""
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def _parse_json_safe(raw: str, default: Any = None) -> Any:
    """Parse JSON from LLM response with fallback."""
    try:
        cleaned = _strip_json_markdown(raw)
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as e:
        if default is not None:
            return default
        # Try to find JSON object in text if mixed with chatter
        try:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        raise ValueError(f"Failed to parse JSON: {e}") from e


# --- Gemini Implementation ---

def _parse_quota_retry_seconds(exc: Exception) -> int:
    msg = str(exc)
    m = re.search(r"[Rr]etry in ([\d.]+)s", msg)
    if m:
        try:
            return min(120, max(1, int(float(m.group(1)) + 1)))
        except ValueError:
            pass
    return 40


def _is_daily_quota_error(exc: Exception) -> bool:
    return "PerDay" in str(exc) or "per_day" in str(exc).lower()


def _get_first_available_model_name() -> Optional[str]:
    try:
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                name = getattr(m, "name", "") or ""
                if name.startswith("models/"):
                    return name.replace("models/", "", 1)
                return name
    except Exception:
        pass
    return None


def _get_alternative_model_name(current: str) -> Optional[str]:
    try:
        candidates = []
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" not in methods:
                continue
            name = getattr(m, "name", "") or ""
            if name.startswith("models/"):
                name = name.replace("models/", "", 1)
            if name and name != current:
                candidates.append(name)
        for c in candidates:
            if "lite" in c.lower() or "flash-lite" in c:
                return c
        return candidates[0] if candidates else None
    except Exception:
        return None


def _get_response_text(response) -> str:
    if response is None:
        return ""
    try:
        pf = getattr(response, "prompt_feedback", None)
        if pf and getattr(pf, "block_reason", None):
            raise ValueError(f"Blocked: {pf.block_reason}")
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise ValueError("No candidates.")
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) if content else []
        if not parts:
            return ""
        texts = []
        for p in parts:
            if hasattr(p, "text") and getattr(p, "text", None):
                texts.append(p.text)
        return "\n".join(texts).strip() if texts else ""
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read API response: {e}") from e


class GeminiLLMService:
    def __init__(self) -> None:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = GEMINI_MODEL.strip() or "gemini-pro"
        if model_name.startswith("models/"):
            model_name = model_name.replace("models/", "", 1)
        self._model_name = model_name
        self._init_model(model_name)

    def _init_model(self, name: str):
        try:
            self.model = genai.GenerativeModel(
                name,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=8192,
                ),
            )
        except Exception:
            fallback = _get_first_available_model_name()
            if fallback:
                self.model = genai.GenerativeModel(
                    fallback,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=8192,
                    ),
                )
                self._model_name = fallback
            else:
                raise

    def _ensure_model(self) -> None:
        fallback = _get_first_available_model_name()
        if fallback and fallback != self._model_name:
            self._init_model(fallback)

    def _generate_with_retry(self, prompt: str):
        try:
            return self.model.generate_content(prompt)
        except google_exceptions.ResourceExhausted as e:
            alt = _get_alternative_model_name(self._model_name)
            if alt:
                try:
                    self._init_model(alt)
                    self._model_name = alt
                    return self.model.generate_content(prompt)
                except google_exceptions.ResourceExhausted:
                    pass
            retry_secs = _parse_quota_retry_seconds(e)
            time.sleep(retry_secs)
            try:
                return self.model.generate_content(prompt)
            except google_exceptions.ResourceExhausted as e2:
                if _is_daily_quota_error(e2):
                    raise ValueError("Daily Gemini quota exceeded.") from e2
                raise ValueError("Gemini quota exceeded.") from e2

    def extract_methodology(self, context: str) -> dict[str, Any]:
        default_result = {
            "datasets": ["Not mentioned"],
            "model": {"name": "Not mentioned", "architecture": "Not mentioned"},
            "metrics": ["Not mentioned"],
            "results": {},
            "summary": "Not available",
        }
        prompt = f"""Extract from this methodology section and return ONLY valid JSON.
If information is not mentioned, use "Not mentioned".

{{
  "datasets": ["dataset name 1", "dataset name 2"],
  "model": {{"name": "model name", "architecture": "architecture description"}},
  "metrics": ["metric1", "metric2"],
  "results": {{}},
  "summary": "• bullet point summary with key details"
}}

Instructions:
- datasets: List of dataset names. Use ["Not mentioned"] if none found
- model: Model name and architecture. Use "Not mentioned" if not found
- metrics: List of evaluation metrics. Use ["Not mentioned"] if none found  
- results: Key numerical results
- summary: Detailed bullet-point summary of methodology (use • for bullets)

Context: {context}
Return only JSON, no markdown."""

        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            if not text:
                return default_result
            data = _parse_json_safe(text, default_result)
            return self._validate_extraction(data, default_result)
        except google_exceptions.NotFound:
            self._ensure_model()
            try:
                response = self._generate_with_retry(prompt)
                text = _get_response_text(response)
                if not text:
                    return default_result
                data = _parse_json_safe(text, default_result)
                return self._validate_extraction(data, default_result)
            except Exception as e2:
                raise ValueError(f"LLM extraction failed: {e2}") from e2
        except Exception as e:
            raise ValueError(f"LLM extraction failed: {e}") from e

    def _validate_extraction(self, data: Any, default: dict) -> dict:
        if not isinstance(data, dict):
            return default
        # Handle old "contribution" key
        if "contribution" in data and "summary" not in data:
            data["summary"] = data.pop("contribution")
        for key in ("datasets", "model", "metrics", "results", "summary"):
            if key not in data:
                data[key] = default[key]
        return data

    def identify_gaps(self, methodologies_list: list[dict[str, Any]]) -> dict[str, Any]:
        default_result = {
            "methodological_gaps": [],
            "dataset_limitations": [],
            "evaluation_gaps": [],
            "novel_directions": [],
        }
        if not methodologies_list:
            return default_result
        papers_json = json.dumps(methodologies_list, indent=2)
        prompt = f"""Analyze these papers and identify research gaps in JSON format:
{{
  "methodological_gaps": [{{"description": "", "explanation": "", "value": ""}}],
  "dataset_limitations": [],
  "evaluation_gaps": [],
  "novel_directions": []
}}
Papers: {papers_json}
Return only JSON."""
        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            if not text:
                return default_result
            data = _parse_json_safe(text, default_result)
            if not isinstance(data, dict):
                return default_result
            for key in default_result:
                if key not in data:
                    data[key] = default_result[key]
            return data
        except Exception as e:
            raise ValueError(f"Gap analysis failed: {e}") from e

    def generate_comparison_table(self, methodologies_list: list[dict[str, Any]]) -> str:
        if not methodologies_list:
            return "(No papers.)"
        papers_json = json.dumps(methodologies_list, indent=2)
        prompt = f"""Create a markdown comparison table with columns:
Paper | Dataset | Model | Metrics | Results | Contribution
Data: {papers_json}
Return only the markdown table."""
        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            return text if text else ""
        except Exception as e:
            raise ValueError(f"Table generation failed: {e}") from e

    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str]:
        """
        Generate summaries for each section of a paper.
        
        Args:
            sections: Dict mapping section names to section text
            
        Returns:
            Dict mapping section names to bullet-point summaries
        """
        summaries = {}
        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue
            prompt = f"""Summarize the following {section_name} section from a research paper.
Create a concise bullet-point summary. Focus on key points and findings.

Section: {section_name}
Text:
{section_text[:3000]}

Return a bullet-point summary:"""
            try:
                response = self._generate_with_retry(prompt)
                text = _get_response_text(response)
                summaries[section_name] = text if text else "No summary available"
            except Exception:
                summaries[section_name] = "Error generating summary"
        return summaries

    def analyze_swot(self, paper_context: str) -> str:
        """
        Generate SWOT analysis for a research paper.
        
        Args:
            paper_context: Full text or key sections of the paper
            
        Returns:
            Markdown-formatted SWOT analysis
        """
        prompt = f"""Analyze this research paper and provide a comprehensive SWOT analysis.

Format your response as markdown with the following structure:

## Strengths (Internal)
- Unique methodology, strong data, clear arguments, novel findings
- [Add 3-5 specific bullet points]

## Weaknesses (Internal)
- Small sample size, limited scope, potential bias, incomplete literature review
- [Add 3-5 specific bullet points]

## Opportunities (External)
- Potential to advance a theory, applicability to industry, building on previous studies
- [Add 3-5 specific bullet points]

## Threats (External)
- Similar competing research, rapid technological changes, conflicting findings, potential misinterpretation
- [Add 3-5 specific bullet points]

Paper Context:
{paper_context[:4000]}

Return ONLY the markdown SWOT analysis."""
        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            return text if text else "SWOT analysis not available"
        except Exception as e:
            raise ValueError(f"SWOT analysis failed: {e}") from e


# --- Ollama Implementation ---

class OllamaLLMService:
    def __init__(self) -> None:
        self.host = OLLAMA_HOST.rstrip("/")
        self.model = OLLAMA_MODEL
        # Check connection immediately? No, let strict lazy loading handle it to avoid init crashes if possible.

    def _generate(self, prompt: str, json_mode: bool = False) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": 4096,
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            r_json = resp.json()
            return r_json.get("response", "")
        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Could not connect to Ollama at {self.host}. "
                "Is Ollama running? (Run `ollama run {self.model}` in terminal)"
            )
        except Exception as e:
            raise ValueError(f"Ollama generation failed: {e}") from e

    def extract_methodology(self, context: str) -> dict[str, Any]:
        default_result = {
            "datasets": ["Not mentioned"],
            "model": {"name": "Not mentioned", "architecture": "Not mentioned"},
            "metrics": ["Not mentioned"],
            "results": {},
            "summary": "Not available",
        }
        prompt = f"""You are a research assistant analyzing a methodology section from a research paper.

Extract the following information from the text. If any information is not explicitly mentioned, use the phrase "Not mentioned".

Return ONLY valid JSON with this exact structure:
{{
  "datasets": ["dataset name 1", "dataset name 2"],
  "model": {{"name": "model name", "architecture": "architecture description"}},
  "metrics": ["metric1", "metric2"],
  "results": {{"key": "value"}},
  "summary": "bullet point summary here"
}}

Instructions:
- datasets: Extract all dataset names mentioned. If none found, return ["Not mentioned"]
- model: Extract the model name and architecture. If not found, use "Not mentioned"
- metrics: Extract all evaluation metrics used. If none found, return ["Not mentioned"]
- results: Extract key numerical results as key-value pairs
- summary: Create a detailed bullet-point summary of the methodology. Use • for bullets. Be comprehensive and include all important details about the approach, architecture, training procedure, and experiments.

Text to analyze:
{context}

Return ONLY the JSON object, no other text."""
        try:
            text = self._generate(prompt, json_mode=True)
            if not text:
                return default_result
            data = _parse_json_safe(text, default_result)
            if not isinstance(data, dict):
                return default_result
            # Ensure all keys exist and handle old "contribution" key
            if "contribution" in data and "summary" not in data:
                data["summary"] = data.pop("contribution")
            for key in default_result:
                if key not in data:
                    data[key] = default_result[key]
            return data
        except Exception as e:
            raise ValueError(f"Ollama extraction error: {e}") from e

    def identify_gaps(self, methodologies_list: list[dict[str, Any]]) -> dict[str, Any]:
        default_result = {
            "methodological_gaps": [],
            "dataset_limitations": [],
            "evaluation_gaps": [],
            "novel_directions": [],
        }
        if not methodologies_list:
            return default_result
        papers_json = json.dumps(methodologies_list)
        prompt = f"""Analyze these research papers and identify gaps.
Output EXACT JSON with these keys: from the list below
- methodological_gaps: list of objects {{description, explanation}}
- dataset_limitations: list of strings
- evaluation_gaps: list of strings
- novel_directions: list of strings

Papers: {papers_json}
"""
        try:
            text = self._generate(prompt, json_mode=True)
            if not text:
                return default_result
            data = _parse_json_safe(text, default_result)
            if not isinstance(data, dict):
                return default_result
            for key in default_result:
                if key not in data:
                    data[key] = default_result[key]
            return data
        except Exception as e:
            raise ValueError(f"Ollama gap analysis error: {e}") from e

    def generate_comparison_table(self, methodologies_list: list[dict[str, Any]]) -> str:
        if not methodologies_list:
            return "(No papers)"
        papers_json = json.dumps(methodologies_list)
        prompt = f"""Create a markdown comparison table summarizing these papers.
Columns: Paper | Dataset | Model | Metrics | Results | Contribution
Data: {papers_json}
Return ONLY the markdown table.
"""
        try:
            return self._generate(prompt, json_mode=False)
        except Exception as e:
            raise ValueError(f"Ollama table generation error: {e}") from e

    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str]:
        """
        Generate summaries for each section of a paper.
        
        Args:
            sections: Dict mapping section names to section text
            
        Returns:
            Dict mapping section names to bullet-point summaries
        """
        summaries = {}
        for section_name, section_text in sections.items():
            if not section_text.strip():
                continue
            prompt = f"""Summarize the following {section_name} section from a research paper.
Create a concise bullet-point summary using • for bullets. Focus on key points and findings.

Section: {section_name}
Text:
{section_text[:3000]}

Return a bullet-point summary (use • for bullets):"""
            try:
                summary = self._generate(prompt, json_mode=False)
                summaries[section_name] = summary if summary else "No summary available"
            except Exception:
                summaries[section_name] = "Error generating summary"
        return summaries

    def analyze_swot(self, paper_context: str) -> str:
        """
        Generate SWOT analysis for a research paper.
        
        Args:
            paper_context: Full text or key sections of the paper
            
        Returns:
            Markdown-formatted SWOT analysis
        """
        prompt = f"""Analyze this research paper and provide a comprehensive SWOT analysis.

Format your response as markdown with the following structure:

## Strengths (Internal)
- List internal strengths: unique methodology, strong data, clear arguments, novel findings
- Provide 3-5 specific bullet points

## Weaknesses (Internal)
- List internal weaknesses: small sample size, limited scope, potential bias, incomplete literature review
- Provide 3-5 specific bullet points

## Opportunities (External)
- List external opportunities: potential to advance theory, industry applicability, building on studies
- Provide 3-5 specific bullet points

## Threats (External)
- List external threats: competing research, tech changes, conflicting findings, misinterpretation risk
- Provide 3-5 specific bullet points

Paper Context:
{paper_context[:4000]}

Return ONLY the markdown SWOT analysis using • for bullets."""
        try:
            text = self._generate(prompt, json_mode=False)
            return text if text else "SWOT analysis not available"
        except Exception as e:
            raise ValueError(f"SWOT analysis failed: {e}") from e


# --- Factory ---

class LLMService:
    def __init__(self):
        self.provider = LLM_PROVIDER.lower()
        if self.provider == "ollama":
            self.backend = OllamaLLMService()
        else:
            self.backend = GeminiLLMService()

    def extract_methodology(self, context: str) -> dict[str, Any]:
        return self.backend.extract_methodology(context)

    def identify_gaps(self, methodologies_list: list[dict[str, Any]]) -> dict[str, Any]:
        return self.backend.identify_gaps(methodologies_list)

    def generate_comparison_table(self, methodologies_list: list[dict[str, Any]]) -> str:
        return self.backend.generate_comparison_table(methodologies_list)

    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str]:
        return self.backend.summarize_sections(sections)

    def analyze_swot(self, paper_context: str) -> str:
        return self.backend.analyze_swot(paper_context)
