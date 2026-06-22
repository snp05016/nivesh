"""
backend/tasks/ — Celery task modules.

Task modules import the shared Celery app from services/celery_tasks.py and
register tasks using ``@app.task(name='tasks.<module>.<task>')`` so they are
addressable by the canonical dotted name.

Run worker:
    celery -A services.celery_tasks worker --loglevel=info -Q alpha158,default
"""
