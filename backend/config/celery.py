"""Celery exclusivo do SGDL — fila e broker isolados de outros apps do servidor."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("sgdl")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
