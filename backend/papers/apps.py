"""
DJANGO APP CONFIGURATION
Project: Research Assistant
File: backend/papers/apps.py
"""
from django.apps import AppConfig


class PapersConfig(AppConfig):
    """Configuration for the Papers application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'papers'
