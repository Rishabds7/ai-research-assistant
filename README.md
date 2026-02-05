# PaperDigest AI - Advanced Research Assistant

A professional, full-stack AI research platform designed to synthesize complex academic papers into actionable insights. PaperDigest AI leverages multi-staged LLM pipelines and RAG (Retrieval-Augmented Generation) to streamline literature reviews and technical deep-dives.

## Features

### 📄 Intelligent Ingestion

- **Structural Extraction** - Automatically segments PDFs into logical sections (Abstract, Introduction, Methodology, etc.).
- **Multi-pass Processing** - Asynchronous extraction of titles, authors, and high-level paper metadata.
- **Smart Formatting** - Cleans raw PDF artifacts and multi-column layouts using PyMuPDF and Regex heuristics.

### 🧠 AI-Driven Analysis

- **Hierarchical Summarization** - Generates section-by-section summaries before synthesizing a final 'Global TL;DR'.
- **Technical Deep-Dives** - Specialized prompts for extracting technical methodologies, model architectures, and metrics.
- **Metadata Tagging** - Automatic identification of research datasets and software licenses used in the study.

### 🔍 Advanced Search & RAG

- **Semantic Search** - Search across your paper library using natural language, powered by vector embeddings.
- **Side-by-Side Review** - Compare AI summaries directly alongside the original PDF text.
- **Context-Aware RAG** - Injects the most relevant snippets from papers into LLM prompts for high-accuracy extraction.

### 📊 Review Dashboard

- **Literature Review Matrix** - A specialized view that aggregates summaries from all your papers into a comparison table.
- **Researcher Notes** - Add personal annotations alongside AI-generated insights.
- **CSV Export** - Export your entire literature review matrix for external analysis or reporting.

### ⚙️ Hybrid AI Backend

- **Cloud Power** - Native support for Google Gemini 1.5 Pro/Flash for high-accuracy processing.
- **Local Privacy** - Built-in integration with Ollama (Llama 3) for offline, privacy-first research analysis.
- **Factory Pattern** - Seamlessly toggle between LLM providers via environment configuration.

## Getting Started

### Prerequisites

- **Docker & Docker Compose** (Recommended)
- **Git**
- **Google Gemini API Key** (Optional, for cloud processing)
- **Ollama** (Optional, for local processing)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Rishabds7/ai-research-assistant.git
   cd ai-research-assistant
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory (refer to `.env.example` in `backend/`):

   ```bash
   # Backend Settings
   GEMINI_API_KEY=your_api_key_here
   LLM_PROVIDER=gemini # or 'ollama'
   
   # Database Settings
   DB_PASSWORD=your_secure_password
   ```

3. **Launch the platform**

   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - **Frontend:** [http://localhost:3000](http://localhost:3000)
   - **Backend API:** [http://localhost:8000/api/](http://localhost:8000/api/)

## Technical Architecture

### Core Technologies

- **Next.js 15 & React 19** - Modern, responsive frontend with Server Components.
- **Django & DRF** - Robust Python backend for API management and data persistence.
- **PostgreSQL & pgvector** - High-performance vector database for semantic search.
- **Celery & Redis** - Distributed task queue for asynchronous AI processing.
- **Tailwind CSS 4** - Premium UI styling with glassmorphism and modern aesthetics.

### Key Components

#### AI Task Orchestration

```
PDF Upload → Celery Worker → PDFProcessor → LLM (Gemini/Ollama) → EmbeddingService → PostgreSQL
```

#### Vector Search Pipeline (RAG)

1. **Embedding**: Convert paper chunks into 384-dimensional vectors via `all-MiniLM-L6-v2`.
2. **Storage**: Vector data persists in PostgreSQL using the `pgvector` extension.
3. **Similarity**: Natural language queries are matched using Cosine Distance (`<=>`).

## File Structure

```
research-assistant-mvp/
├── backend/            # Django Application
│   ├── core/           # Project settings & Celery config
│   ├── papers/         # Models, Views, and Tasks
│   └── services/       # Core AI/PDF Logic (LLM, Embeddings, PDFProcessor)
├── frontend/           # Next.js Application
│   ├── src/app/        # Pages & Layouts
│   ├── src/components/ # Atomic UI components
│   └── src/lib/        # API client & utility functions
├── docker-compose.yml  # Orchestration for DB, Redis, Worker, and Apps
└── README.md           # Professional Documentation
```

## Browser Compatibility

- ✅ Chrome 110+
- ✅ Firefox 100+
- ✅ Safari 16+
- ✅ Edge 110+

## Development & Testing

### Key Backend Services

- `services.pdf_processor.PDFProcessor` - Text segmentation logic.
- `services.llm_service.LLMService` - Multi-provider (Gemini/Ollama) factory.
- `services.embedding_service.EmbeddingService` - Vectorization and RAG logic.

### API Documentation

The API documentation is available via Swagger/ReDoc at `/api/docs/` when the backend is running.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-ai-tool`)
3. Commit your changes (`git commit -m 'Add amazing AI feature'`)
4. Push to the branch (`git push origin feature/amazing-ai-tool`)
5. Open a Pull Request

---

**PaperDigest AI** - Synthesizing deep research into actionable insights.
