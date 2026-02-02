"""
Gap analysis service: dataset/model combinations and common limitations.
Works on extracted methodology dicts (no LLM).
"""

import re
from collections import Counter
from typing import Any


class GapAnalyzer:
    """Analyze methodologies for missing combinations and common limitations."""

    def analyze_combinations(
        self, methodologies: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Extract unique datasets and models; find which combinations exist;
        return missing (dataset, model) combinations.

        Args:
            methodologies: List of methodology dicts (each has datasets, model).

        Returns:
            Dict with: unique_datasets, unique_models, existing_combinations,
                       missing_combinations (list of {dataset, model}).
        """
        datasets: set[str] = set()
        models: set[str] = set()
        existing: set[tuple[str, str]] = set()

        for m in methodologies:
            # Model name
            model_info = m.get("model") or {}
            if isinstance(model_info, dict):
                name = (model_info.get("name") or "").strip()
            else:
                name = str(model_info).strip()
            if name:
                models.add(name)

            # Datasets
            ds_list = m.get("datasets") or []
            if not isinstance(ds_list, list):
                continue
            for d in ds_list:
                if isinstance(d, dict):
                    ds_name = (d.get("name") or "").strip()
                else:
                    ds_name = str(d).strip()
                if ds_name:
                    datasets.add(ds_name)
                    existing.add((ds_name, name)) if name else None

        # Missing: every (dataset, model) that is in cross-product but not in existing
        missing_combinations: list[dict[str, str]] = []
        for ds in datasets:
            for mod in models:
                if (ds, mod) not in existing:
                    missing_combinations.append({"dataset": ds, "model": mod})

        return {
            "unique_datasets": list(datasets),
            "unique_models": list(models),
            "existing_combinations": [
                {"dataset": d, "model": m} for d, m in existing
            ],
            "missing_combinations": missing_combinations,
        }

    def extract_common_limitations(
        self, methodologies: list[dict[str, Any]]
    ) -> list[str]:
        """
        Look for common phrases in results/contribution/conclusion-like fields.
        Returns list of limitation-like patterns (e.g. short phrases).

        Args:
            methodologies: List of methodology dicts (may have results, contribution).

        Returns:
            List of strings (limitation patterns).
        """
        # Collect text from results and contribution
        texts: list[str] = []
        for m in methodologies:
            for key in ("results", "contribution", "metrics"):
                val = m.get(key)
                if isinstance(val, str) and val.strip():
                    texts.append(val.strip().lower())
                elif isinstance(val, dict):
                    texts.append(" ".join(str(v) for v in val.values()).lower())
                elif isinstance(val, list) and val:
                    texts.append(" ".join(str(v) for v in val).lower())

        if not texts:
            return []

        # Simple phrase extraction: 3–6 word sequences
        phrase_counts: Counter = Counter()
        for text in texts:
            words = re.findall(r"\b\w+\b", text)
            for n in (4, 5, 6):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i : i + n])
                    if len(phrase) > 15:
                        phrase_counts[phrase] += 1

        # Return phrases that appear in more than one paper (limitation-like)
        threshold = max(1, len(methodologies) // 2)
        common = [p for p, c in phrase_counts.most_common(30) if c >= threshold]
        return common[:15]
