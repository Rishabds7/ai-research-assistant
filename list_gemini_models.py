"""
List Gemini models available for your API key that support generateContent.
Run from project root with .env loaded: python list_gemini_models.py

Add one of the printed model names to your .env as GEMINI_MODEL=...
"""

import os
import sys

# Load .env from project root
from pathlib import Path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import google.generativeai as genai

api_key = os.getenv("GEMINI_API_KEY", "").strip()
if not api_key:
    print("ERROR: GEMINI_API_KEY not set in .env")
    sys.exit(1)

genai.configure(api_key=api_key)

print("Models that support generateContent (use one as GEMINI_MODEL in .env):\n")
count = 0
for m in genai.list_models():
    methods = getattr(m, "supported_generation_methods", []) or []
    if "generateContent" in methods:
        name = getattr(m, "name", "") or ""
        # name is like "models/gemini-1.5-flash-8b" - for .env use the short name
        short = name.replace("models/", "") if name else ""
        print(f"  {short}")
        count += 1

if count == 0:
    print("  (none found - check your API key and region)")
else:
    print(f"\n({count} model(s)). Add to .env: GEMINI_MODEL=<one of the names above>")
