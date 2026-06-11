try:
    from .celery import app as celery_app
except ImportError:  # Celery opcional em dev sem worker
    celery_app = None

__all__ = ("celery_app",)
