"""
LLM service: supports Google Gemini and Ollama.
"""

import json
import re
import time
import logging
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)

import google.generativeai as genai
import requests
from google.api_core import exceptions as google_exceptions

from django.conf import settings

# These are defaults, but we will re-read them in the service to be safe
_GEMINI_API_KEY = settings.GEMINI_API_KEY
_GEMINI_MODEL = settings.GEMINI_MODEL
_LLM_PROVIDER = settings.LLM_PROVIDER
_OLLAMA_HOST = settings.OLLAMA_HOST
_OLLAMA_MODEL = settings.OLLAMA_MODEL



class LLMBackend(Protocol):
    def extract_methodology(self, context: str) -> dict[str, Any]: ...
    def identify_gaps(self, methodologies_list: list[dict[str, Any]]) -> dict[str, Any]: ...
    def generate_comparison_table(self, methodologies_list: list[dict[str, Any]]) -> str: ...
    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str]: ...
    def extract_datasets(self, context: str) -> list[str]: ...
    def extract_licenses(self, context: str) -> list[str]: ...


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
    if not raw:
        return default if default is not None else []
    
    cleaned = _strip_json_markdown(raw)
    
    try:
        # Attempt direct parse first
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # Try to find JSON object or list in text if mixed with chatter
        try:
            # Use regex to find the first '{' or '[' and the last '}' or ']'
            dict_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            list_match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
            
            parsed = None
            # If both found, pick the one that starts earlier
            if dict_match and list_match:
                if dict_match.start() < list_match.start():
                    parsed = json.loads(dict_match.group(1))
                else:
                    parsed = json.loads(list_match.group(1))
            elif dict_match:
                parsed = json.loads(dict_match.group(1))
            elif list_match:
                parsed = json.loads(list_match.group(1))
            
            if parsed is not None:
                # Shared logic for dict unpacking: if model returns {"datasets": [...]}
                if isinstance(parsed, dict):
                    for key in ["datasets", "dataset_names", "dataset", "dataset_list", "items", "data", "results"]:
                        if key in parsed and isinstance(parsed[key], list):
                            return parsed[key]
                return parsed
        except Exception:
            pass

        if default is not None:
            return default
        raise ValueError(f"Failed to parse JSON: {e}") from e


def clean_llm_summary(text: str) -> str:
    """
    Remove LLM meta-talk and disclaimers from the summary.
    """
    if not text:
        return ""
        
    lines = text.split('\n')
    cleaned_lines = []
    
    meta_patterns = [
        r"these bullet points only summarize",
        r"do not include any analysis",
        r"summary of the .* section",
        r"here are the detailed bullet points",
        r"based on the provided text",
        r"summarize only based on",
        r"i have summarized",
        r"the following bullet points",
        r"not explicitly mentioned in the text",
        r"return only bullet points",
        r"return only the bullet points",
        r"note: these bullet points",
        r"note: summaries are based",
        r"bullet points are based solely on the provided text",
        r"here are the concise bullet points",
        r"here are the extremely detailed",
        r"summarizing the unique problem",
        r"summarizing the introduction",
        r"summarizing the methodology",
        r"summarizing the results"
    ]
    
    for line in lines:
        cleaned_line = line
        # Remove common "Note: ..." suffixes from the end of a line if they exist
        if "Note:" in cleaned_line:
            parts = cleaned_line.split("Note:", 1)
            # If there's something before "Note:", keep it. If not, this might be a meta line.
            if parts[0].strip() and len(parts[0].strip()) > 10:
                cleaned_line = parts[0].strip()
            else:
                continue # Skip the line if it's just "Note: ..."

        stripped = cleaned_line.strip().lower()
        if not stripped:
            continue
            
        is_meta = False
        for pattern in meta_patterns:
            # If the pattern accounts for more than 50% of the line, it's a meta line
            if re.search(pattern, stripped):
                is_meta = True
                break
        
        if not is_meta:
            cleaned_lines.append(cleaned_line)
            
    return '\n'.join(cleaned_lines)


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

    def extract_datasets(self, context: str) -> list[str]:
        prompt = f"""You are a research assistant. Your task is to extract the names of ALL datasets used for training, evaluation, or benchmarking in this research paper.

        CRITICAL INSTRUCTIONS:
        1. Contextual Understanding: Scan for patterns like:
           - "Evaluated on [Name]..."
           - "Figure 1 shows performance on [Name]..."
           - "Using [Name] dataset (size)..."
           - "Trained on [Name] and [Name]..."
           - "Following prior work (Hu et al. 2024), we use the [Name] benchmark..."
        2. Scope: Look at Abstract, Introduction, AND specifically Experimental Setup/Evaluation sections.
        3. Medical Focus: Specifically look for benchmarks like "MIMIC-CXR", "CheXpert", "BraTS", "SLAKE", "VQA-RAD", "PathVQA", "Quilt-VQA", etc.
        4. Detail: Include the version or size if mentioned (e.g., "MIMIC-CXR v2.0").
        5. Exclusion: Do NOT include model names (like ResNet, BERT, or the model being proposed in the paper).
        
        Return ONLY a valid JSON list of strings. 
        Example Output: ["MIMIC-CXR (369K)", "CheXpert (191K)", "SLAKE", "VQA-RAD"]
        
        If absolutely no dataset names are detected, return ["None mentioned"].
        
        Text to Analyze:
        {context[:80000]}
        
        JSON list:"""
        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            data = _parse_json_safe(text, [])
            if isinstance(data, list) and len(data) > 0:
                # Filter out garbage
                cleaned = [d.strip() for d in data if d and d.lower() != "none mentioned" and len(d) > 1]
                return cleaned if cleaned else ["None mentioned"]
            return ["None mentioned"]
        except Exception:
            return ["None mentioned"]

    def extract_licenses(self, context: str) -> list[str]:
        prompt = f"""Identify any software or data licenses mentioned in the following text (e.g. Apache 2.0, MIT, Creative Commons, CC-BY, etc.).
Return ONLY as a JSON list of strings.
If none mentioned, return ["None mentioned"].

Text:
{context[:8000]}

JSON list:"""
        try:
            response = self._generate_with_retry(prompt)
            text = _get_response_text(response)
            data = _parse_json_safe(text, [])
            return data if (isinstance(data, list) and len(data) > 0) else ["None mentioned"]
        except Exception:
            return ["None mentioned"]

    def smart_summarize_paper(self, full_text: str, existing_sections: dict[str, str] = None) -> dict[str, str]:
        """
        Group natural sections into logical buckets, summarize them, and ensure
        a strict logical order. Skips everything after "References".
        """
        if not existing_sections:
            return {"Abstract": "No sections detected to summarize."}

        # 1. Define logical buckets and their mapping keywords
        logical_order = [
            "Abstract",
            "Introduction",
            "Background",
            "Methodology",
            "Results",
            "Conclusion",
            "References"
        ]
        
        mapping = {
            "Abstract": ["abstract", "summary"],
            "Introduction": ["introduction", "preface"],
            "Background": ["background", "related work", "literature review", "preliminaries", "problem statement"],
            "Methodology": ["method", "approach", "system", "architecture", "algorithm", "design", "implementation", "model"],
            "Results": ["result", "experiment", "evaluation", "analysis", "finding", "performance"],
            "Conclusion": ["conclusion", "discussion", "future work"],
            "References": ["reference", "bibliography"]
        }

        # 2. Filter sections: Stop at "References" and bucket them
        buckets = {cat: "" for cat in logical_order}
        found_references = False
        
        # We assume existing_sections matches the order in the paper
        for name, text in existing_sections.items():
            name_lower = name.lower()
            
            # Stop if we hit something after references but before we have references
            if found_references and not any(k in name_lower for k in mapping["References"]):
                 # Skip acknowledgments, appendices etc that come after references
                 if any(skip in name_lower for skip in ["acknowledgments", "appendix", "author"]):
                     continue

            target_cat = None
            for cat, keywords in mapping.items():
                if any(k in name_lower for k in keywords):
                    target_cat = cat
                    if cat == "References":
                        found_references = True
                    break
            
            if target_cat:
                buckets[target_cat] += f"\n\n### {name}\n{text}"
            else:
                # Fallback: if it sounds technical, put in Methodology
                if any(k in name_lower for k in ["graph", "pipeline", "network", "layer"]):
                    buckets["Methodology"] += f"\n\n### {name}\n{text}"
                else:
                    # Otherwise put in Background or Introduction depending on position?
                    # For now, put in Background as a safe "general content" bucket
                    buckets["Background"] += f"\n\n### {name}\n{text}"

        # 3. Summarize each bucket
        final_summaries = {}
        for cat in logical_order:
            content = buckets[cat].strip()
            
            # FOE METHODOLOGY: if missing, deep-search
            if cat == "Methodology" and not content:
                logger.info("Methodology bucket empty. Performing deep-search...")
                search_prompt = f"Extract the core technical architecture, algorithms, or methodology from the following research paper text. Focus on EXACTLY how it works.\n\nText:\n{full_text[:30000]}"
                try:
                    resp = self._generate_with_retry(search_prompt)
                    content = _get_response_text(resp)
                except Exception:
                    pass

            if not content:
                # If cat is Introduction or Conclusion, we might want to try to fill it
                if cat in ["Introduction", "Conclusion"]:
                    # Try a smaller slice
                    content = full_text[:4000] if cat == "Introduction" else full_text[-4000:]
                else:
                    continue

            # High Quality Prompt
            depth_instr = "Create 4-6 EXTREMELY DETAILED, TECHNICAL bullet points (•). Focus on quantitative data, specific algorithms, and core contributions."
            if cat == "Methodology":
                depth_instr += " Explain the technical architecture, mathematical formulations, and logistical data flow. Avoid generic fluff."
            elif cat == "Abstract":
                depth_instr = "Create 3-5 concise bullet points summarizing the unique problem, the proposed solution, and the key result."

            prompt = f"""Summarize the '{cat}' of this research paper based on the text provided.
{depth_instr}

STRICT GROUNDING: Use ONLY the provided text. Do NOT hallucinate names or external examples (e.g., do NOT mention 'NeoChip' or 'Pablo Picasso' unless they are in the text below).
Combine related subsections into a cohesive summary.

Text:
{content[:12000]}

Return ONLY the bullet points:"""

            try:
                response = self._generate_with_retry(prompt)
                summary = _get_response_text(response)
                if summary:
                    final_summaries[cat] = clean_llm_summary(summary)
            except Exception as e:
                logger.error(f"Error summarizing bucket {cat}: {e}")

        # 4. Final Polish: Ensure order and no empty summaries
        ordered_summaries = {}
        for cat in logical_order:
            if cat in final_summaries:
                ordered_summaries[cat] = final_summaries[cat]
            elif cat == "Methodology": # Always include Methodology
                ordered_summaries[cat] = "No specific methodology section was detected, but the paper discusses general techniques."
        
        return ordered_summaries

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


# --- Ollama Implementation ---

class OllamaLLMService:
    def __init__(self) -> None:
        from django.conf import settings
        self.host = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434').rstrip("/")
        self.model = getattr(settings, 'OLLAMA_MODEL', 'llama3')


    def _generate(self, prompt: str, json_mode: bool = False) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192,
            }
        }
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            r_json = resp.json()
            response_text = r_json.get("response", "")
            
            # DEBUG: Log raw response to a file we can read
            try:
                with open("ollama_debug.log", "a") as f:
                    f.write(f"\n\n--- PROMPT ---\n{prompt[:200]}...\n")
                    f.write(f"--- RESPONSE ---\n{response_text}\n")
            except Exception:
                pass
                
            return response_text
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

    def extract_datasets(self, context: str) -> list[str]:
        prompt = f"""You are a research assistant. Read the following text from a research paper and extract the names of only ACTUAL research datasets used for training, evaluation, or as benchmarks.

CRITICAL EXCLUSION RULES:
1. Do NOT include Model names or Architectures (e.g., skip 'EfficientNet-L2', 'ResNeXt101', 'GPT-2', 'BERT').
2. Do NOT include Training algorithms or Methods (e.g., skip 'Noisy Student', 'Contrastive Learning').
3. Do NOT include general Platforms/Sources unless they are formal datasets (e.g., skip 'Instagram', 'Twitter', 'Social Media' unless referring to a specific versioned benchmark like 'Instagram-1B').

Look for:
- Formally named research benchmarks and corpora.
- Proper nouns often followed by "dataset", "corpus", "benchmark", or "data".
- Specific medical benchmarks: MIMIC-CXR, CheXpert, SLAKE, VQA-RAD, PATHVQA, Quilt-VQA, MedVQA.

Context:
{context[:25000]}

Return ONLY a valid JSON list of strings.
Example: ["SQuAD v2.0", "MS-COCO", "ImageNet"]

STRICT DATASET POLICY:
- If NO proper dataset names (like MIMIC, CheXpert, etc.) are explicitly mentioned in the context above, you MUST return ["None mentioned"].
- DO NOT assume a medical paper uses MIMIC-CXR. ONLY include it if mentioned.
- If no specific datasets are mentioned, return ["None mentioned"].
"""
        try:
            text = self._generate(prompt, json_mode=True)
            data = _parse_json_safe(text, [])
            
            # Handle if LLM returned a dict with a key
            if isinstance(data, dict):
                for key in ["datasets", "dataset_names", "dataset", "dataset_list", "items", "data"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
            
            if isinstance(data, list) and len(data) > 0:
                # Filter out garbage and "None mentioned" if mixed
                cleaned = [str(d).strip() for d in data if d and str(d).lower() != "none mentioned"]
                return cleaned if cleaned else ["None mentioned"]
            
            return ["None mentioned"]
        except Exception as e:
            logger.error(f"Ollama dataset extraction error: {e}")
            return ["None mentioned"]

    def extract_licenses(self, context: str) -> list[str]:
        prompt = f"""You are a research assistant. Identify any software or data licenses mentioned in this research paper text (e.g. MIT, Apache 2.0, Creative Commons, CC-BY, GNU GPL).
Look for mentions of "licensed under", "available under", "copyright".

Context:
{context[:8000]}

Return ONLY a valid JSON list of strings.
Example: ["CC BY 4.0", "Apache 2.0"]
If no specific licenses are mentioned, return ["None mentioned"].
"""
        try:
            text = self._generate(prompt, json_mode=True)
            data = _parse_json_safe(text, [])
            
            if isinstance(data, dict):
                for key in ["licenses", "license_names", "items", "data"]:
                    if key in data and isinstance(data[key], list):
                        data = data[key]
                        break
            
            if isinstance(data, list) and len(data) > 0:
                cleaned = [str(d).strip() for d in data if d and str(d).lower() != "none mentioned"]
                return cleaned if cleaned else ["None mentioned"]
            
            return ["None mentioned"]
        except Exception as e:
            logger.error(f"Ollama license extraction error: {e}")
            return ["None mentioned"]

    def smart_summarize_paper(self, full_text: str, existing_sections: dict[str, str] = None) -> dict[str, str]:
        """
        Group natural sections into logical buckets for Ollama.
        """
        if not existing_sections:
            return {"Abstract": "No sections detected."}

        logical_order = [
            "Abstract", "Introduction", "Background", 
            "Methodology", "Results", "Conclusion", "References"
        ]
        
        mapping = {
            "Abstract": ["abstract", "summary"],
            "Introduction": ["introduction"],
            "Background": ["background", "related work", "literature review", "preliminaries"],
            "Methodology": ["method", "approach", "system", "architecture", "algorithm", "design"],
            "Results": ["result", "experiment", "evaluation", "analysis"],
            "Conclusion": ["conclusion", "discussion", "future work"],
            "References": ["reference", "bibliography"]
        }

        buckets = {cat: "" for cat in logical_order}
        found_references = False

        for name, text in existing_sections.items():
            name_lower = name.lower()
            if found_references and not any(k in name_lower for k in mapping["References"]):
                 if any(skip in name_lower for skip in ["acknowledgments", "appendix"]):
                     continue

            target_cat = None
            for cat, keywords in mapping.items():
                if any(k in name_lower for k in keywords):
                    target_cat = cat
                    if cat == "References":
                        found_references = True
                    break
            
            if target_cat:
                buckets[target_cat] += f"\n\n### {name}\n{text}"
            elif any(k in name_lower for k in ["graph", "model", "pipeline"]):
                buckets["Methodology"] += f"\n\n### {name}\n{text}"

        final_summaries = {}
        for cat in logical_order:
            content = buckets[cat].strip()
            if cat == "Methodology" and not content:
                search_prompt = f"Extract the core technical architecture or methodology from this paper.\n\nText:\n{full_text[:12000]}"
                try:
                    content = self._generate(search_prompt, json_mode=False)
                except Exception:
                    pass

            if not content: continue

            if cat == "Methodology":
                prompt = f"""Summarize the 'Methodology' of this research paper based on the text below.
Create 4-6 EXTREMELY DETAILED, TECHNICAL bullet points (•). 
Focus on explaining:
- The core architecture or model design.
- Specific algorithms, mathematical formulations, or technical pipelines.
- Experimental setup and implementation details.

Text:
{content[:8000]}

Return ONLY the detailed bullet points:"""
            else:
                prompt = f"""Summarize the '{cat}' of this research paper using the text provided.
Create 4-6 concise bullet-points (•) focusing on the most important information.

STRICT GROUNDING: Use ONLY the provided text. Close the gaps between related subsections.

Text:
{content[:4000]}

Return ONLY the bullet points:"""

            try:
                summary = self._generate(prompt, json_mode=False)
                if summary:
                    final_summaries[cat] = clean_llm_summary(summary)
            except Exception:
                pass

        return {cat: final_summaries[cat] for cat in logical_order if cat in final_summaries}



    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str] :
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


# --- Factory ---

class LLMService:
    def __init__(self):
        from django.conf import settings
        self.provider = getattr(settings, 'LLM_PROVIDER', 'ollama').lower()
        logger.info(f"Initializing LLMService with provider: {self.provider}")
        
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

    def smart_summarize_paper(self, full_text: str, existing_sections: dict[str, str] = None) -> dict[str, str]:
        return self.backend.smart_summarize_paper(full_text, existing_sections)

    def summarize_sections(self, sections: dict[str, str]) -> dict[str, str]:
        return self.backend.summarize_sections(sections)

    def extract_datasets(self, context: str) -> list[str]:
        return self.backend.extract_datasets(context)

    def extract_licenses(self, context: str) -> list[str]:
        return self.backend.extract_licenses(context)
