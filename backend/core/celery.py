"""
CELERY TASK BROKER CONFIG
Project: Research Assistant
File: backend/core/celery.py

This file initializes the background task worker system.
It allows us to run heavy AI tasks (like processing PDFs) without slowing down the web server.
"""

import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('research_assistant')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
