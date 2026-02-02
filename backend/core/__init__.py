"""
Core app initialization - imports Celery for Django startup.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
