# Research Assistant MVP (AI Analysis Tool)
**Status:** Multi-feature development in progress (Summarization, Dataset Extraction, Git Integration)
*Last Updated: February 2026*

MVP for analyzing research papers: upload PDFs, extract methodologies (RAG), identify research gaps, and generate comparison tables.

## Tech stack

- **Frontend:** Streamlit  
- **LLM:** Google Gemini 2.0 Flash (`google-generativeai`)  
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`)  
- **Vector DB:** FAISS (in-memory, IndexFlatL2, dim=384)  
- **PDF:** PyMuPDF (`import fitz`)

## Setup

1. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

### If you get "429 quota exceeded"

The app will automatically wait (about 35 seconds) and retry once. If it still fails, wait a minute and try again, or check [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and your usage at [ai.dev/rate-limit](https://ai.dev/rate-limit).

### If you get "404 model not found"

The app will try to auto-select the first available Gemini model. To see which models your API key can use, run:
   ```bash
   python list_gemini_models.py
   ```
   Then set one of the printed names in `.env`: `GEMINI_MODEL=gemini-1.5-flash-8b` (or whatever the script shows).

## Project structure

- `config/` – settings and paths  
- `services/` – PDF processing, embeddings, LLM, gap analysis  
- `utils/` – Excel export  
- `data/uploads/` – uploaded PDFs  
- `data/processed/` – extracted text/sections (JSON)

## Testing checklist

- [ ] Upload single PDF works  
- [ ] Upload multiple PDFs works  
- [ ] Methodology extraction returns valid JSON  
- [ ] Gap analysis works with 2+ papers  
- [ ] Comparison table generates correctly  
- [ ] Excel export downloads  
- [ ] Error messages show for invalid PDFs  
