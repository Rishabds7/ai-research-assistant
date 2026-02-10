"""
PROJECT SETTINGS
Project: Research Assistant
File: backend/core/settings.py

This is the central configuration file for the Django backend.
It defines:
1. Database connections (Postgres).
2. Third-party integrations (Celery, Redis).
3. AI Provider settings (Gemini, Ollama).
4. Security and Middleware policies.
"""

import os
from pathlib import Path
import environ

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False)
)
# Check multiple locations for .env
env_locations = [
    os.path.join(BASE_DIR, '.env'),
    os.path.join(BASE_DIR.parent, '.env'),
    os.path.join(os.getcwd(), '.env'),
]
for loc in env_locations:
    try:
        if os.path.exists(loc):
            environ.Env.read_env(loc)
            break
    except Exception as e:
        print(f"Warning: Could not read .env at {loc}: {e}")

# Security
SECRET_KEY = env('SECRET_KEY', default='django-insecure-fallback-key-for-migrations-only')
DEBUG = env('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'corsheaders',
    'django_celery_results',
    
    # Local apps
    'papers',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database Configuration - PostgreSQL with pgvector support
if env('DATABASE_URL', default=''):
    DATABASES = {
        'default': env.db_url('DATABASE_URL')
    }
else:
    # Fallback for local Docker development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME', default='research_assistant'),
            'USER': env('DB_USER', default='postgres'),
            'PASSWORD': env('DB_PASSWORD', default='postgrespassword'),
            'HOST': env('DB_HOST', default='research_db'),
            'PORT': env('DB_PORT', default='5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True
# Explicitly allow the custom session header needed for isolation
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-session-id',
    'content-disposition',
    'cache-control',
    'pragma',
    'expires',
]

# Allow embedding PDFs in iframes
# (Middleware removed)

# Celery Configuration
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
REDIS_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Custom settings for LLM services
LLM_PROVIDER = env('LLM_PROVIDER', default='ollama')
GEMINI_API_KEY = env('GEMINI_API_KEY', default=env('GOOGLE_API_KEY', default=''))
# Ensure Google SDK can find the key under its preferred name in all contexts
if GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY
GEMINI_MODEL = env('GEMINI_MODEL', default='gemini-2.0-flash')
OLLAMA_HOST = env('OLLAMA_HOST', default='http://localhost:11434')
OLLAMA_MODEL = env('OLLAMA_MODEL', default='llama3')
