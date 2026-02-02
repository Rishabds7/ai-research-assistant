# Research Assistant - Full Stack Migration Plan

## Project Structure
```
research-assistant-mvp/
├── backend/                  # Django backend
│   ├── manage.py
│   ├── core/                # Django project settings
│   ├── api/                 # REST API app
│   ├── papers/              # Papers app (models, services)
│   ├── tasks/               # Celery tasks
│   ├── services/            # Business logic (PDF, LLM, embeddings)
│   └── requirements.txt
│
├── frontend/                # Next.js frontend
│   ├── src/
│   │   ├── app/            # Next.js 14 app router
│   │   ├── components/     # React components
│   │   ├── lib/            # Utilities, API client
│   │   └── types/          # TypeScript types
│   ├── public/
│   └── package.json
│
├── docker-compose.yml       # Local development setup
└── README.md
```

## Implementation Steps

### Phase 1: Backend Setup (Django + PostgreSQL)
1. ✅ Create Django project structure
2. ✅ Setup PostgreSQL with pgvector
3. ✅ Create models (Paper, Methodology, Gap, etc.)
4. ✅ Setup Django REST Framework
5. ✅ Migrate existing services (PDF, LLM, embeddings)

### Phase 2: Celery Integration
1. ✅ Setup Redis for broker
2. ✅ Create Celery tasks for:
   - PDF processing
   - Methodology extraction
   - Gap analysis
   - Comparison table generation
3. ✅ Add task status tracking

### Phase 3: API Endpoints
1. ✅ POST /api/papers/upload
2. ✅ GET /api/papers/
3. ✅ POST /api/papers/{id}/extract-methodology
4. ✅ POST /api/papers/extract-all-sections
5. ✅ POST /api/gaps/analyze
6. ✅ POST /api/comparison/generate
7. ✅ GET /api/tasks/{task_id}/status

### Phase 4: Frontend (Next.js)
1. ✅ Create Next.js 14 project with TypeScript
2. ✅ Setup Tailwind CSS + shadcn/ui
3. ✅ Build UI components:
   - File upload with drag & drop
   - Paper list
   - Methodology display
   - Section summaries
   - Gap analysis view
   - Comparison table
4. ✅ Implement API client
5. ✅ Add real-time status updates

### Phase 5: Integration & Testing
1. ✅ End-to-end testing
2. ✅ Error handling
3. ✅ Loading states
4. ✅ Documentation

## Technology Stack

### Backend
- Django 5.0
- Django REST Framework 3.14
- PostgreSQL 15 + pgvector
- Celery 5.3
- Redis 7.0
- Python 3.9+

### Frontend
- Next.js 14 (App Router)
- TypeScript 5
- Tailwind CSS 3
- shadcn/ui
- Axios/React Query

### Services (Migrated from Streamlit)
- PyMuPDF (PDF processing)
- sentence-transformers (embeddings)
- Ollama/Gemini (LLM)
- OpenPyXL (Excel export)

## Database Schema

### Papers
- id (UUID)
- filename (string)
- uploaded_at (datetime)
- processed (boolean)
- sections (JSON)
- full_text (text)

### Methodologies
- id (UUID)
- paper_id (FK)
- datasets (JSON)
- model (JSON)
- metrics (JSON)
- summary (text)
- created_at (datetime)

### SectionSummaries
- id (UUID)
- paper_id (FK)
- section_name (string)
- summary (text)

### Embeddings (pgvector)
- id (UUID)
- paper_id (FK)
- section_name (string)
- text (text)
- embedding (vector(384))

### TaskStatus
- id (UUID)
- task_id (string, unique)
- task_type (string)
- status (enum: pending, running, completed, failed)
- result (JSON)
- error (text)
- created_at (datetime)
- updated_at (datetime)

## API Design

### Papers API
```
POST   /api/papers/upload/              - Upload PDF
GET    /api/papers/                     - List all papers
GET    /api/papers/{id}/                - Get paper details
DELETE /api/papers/{id}/                - Delete paper
POST   /api/papers/{id}/extract/        - Extract methodology
POST   /api/papers/extract-all/         - Extract all sections (bulk)
```

### Analysis API
```
POST /api/analysis/gaps/                - Analyze research gaps
POST /api/analysis/comparison/          - Generate comparison table
GET  /api/analysis/export/              - Export to Excel
```

### Tasks API
```
GET /api/tasks/{task_id}/               - Get task status
```

## Development Workflow

1. Start PostgreSQL & Redis (via Docker Compose)
2. Run Django migrations
3. Start Celery worker
4. Start Django dev server
5. Start Next.js dev server
6. Access at http://localhost:3000

## Deployment Considerations

- Docker containers for all services
- Nginx for reverse proxy
- Gunicorn for Django
- Supervisor/systemd for Celery workers
- Environment variables for secrets
- PostgreSQL backups
- Redis persistence
