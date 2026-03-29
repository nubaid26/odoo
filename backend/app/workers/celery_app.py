# backend/app/workers/celery_app.py
"""
Celery 5 configuration with 4 named queues: ocr, trust, validation, notifications.
Broker: Redis DB0. Backend: Redis DB1. Serializer: JSON. Results expire: 86400s.
"""

from __future__ import annotations

import os

from celery import Celery
from kombu import Queue

# Read broker/backend from env — these are set in .env
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery(
    "trustflow",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Results
    result_expires=86400,  # 24 hours

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Queues
    task_queues=(
        Queue("ocr", routing_key="ocr"),
        Queue("validation", routing_key="validation"),
        Queue("trust", routing_key="trust"),
        Queue("notifications", routing_key="notifications"),
    ),

    # Default queue (fallback)
    task_default_queue="ocr",
    task_default_routing_key="ocr",

    # Task routes
    task_routes={
        "app.workers.ocr_worker.*": {"queue": "ocr"},
        "app.workers.validation_worker.*": {"queue": "validation"},
        "app.workers.trust_worker.*": {"queue": "trust"},
        "app.workers.notification_worker.*": {"queue": "notifications"},
    },

    # Worker
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Tracking
    task_track_started=True,
    task_acks_late=True,
)

# Auto-discover tasks in workers package
celery_app.autodiscover_tasks(["app.workers"])
