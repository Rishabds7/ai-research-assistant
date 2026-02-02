# Research Assistant MVP (Full Stack)

This is a full-stack research assistant application that migrates the original Streamlit prototype to a robust Django + Next.js architecture.

## Tech Stack

- **Frontend**: Next.js 14, Tailwind CSS, Shadcn/UI (TypeScript)
- **Backend**: Django 4.2, Django REST Framework (Python 3.9+)
- **Database**: PostgreSQL with `pgvector` for vector embeddings
- **Async Queue**: Celery + Redis
- **AI/ML**: 
  - Sentence Transformers (`all-MiniLM-L6-v2`) for local embeddings
  - Ollama / Google Gemini for LLM inference

## Architecture

1. **Upload**: PDF uploaded via Frontend -> Backend.
2. **Processing**: Backend triggers Celery task -> Extracts text -> Computed Embeddings -> Stored in Postgres.
3. **Extraction**: User requests extraction -> Celery task runs LLM over text/embeddings -> Saves extraction to DB.
4. **Analysis**: Separate tasks for Gap Analysis and Comparisons.

## Setup Instructions

### 1. Start Infrastructure (DB & Redis)
```bash
docker-compose up -d
```

### 2. Backend Setup
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Run migrations (ensure Docker is up first!)
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start Celery Worker (Terminal 2)
celery -A core worker -l info

# Start Django Server (Terminal 1)
python manage.py runserver
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to access the application.
