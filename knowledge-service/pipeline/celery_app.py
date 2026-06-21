from celery import Celery

from core.config import settings

celery_app = Celery(
    "knowledge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["pipeline.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_max_tasks_per_child=200,
    task_routes={
        "pipeline.tasks.parse_document": {"queue": "ingest"},
        "pipeline.tasks.chunk_and_embed": {"queue": "ingest"},
        "pipeline.tasks.build_graph": {"queue": "graph"},
        "pipeline.tasks.reindex_document": {"queue": "ingest"},
    },
)
