from celery import Celery
from celery.signals import after_setup_logger

from core.config import settings

celery_app = Celery(
    "knowledge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["pipeline.tasks", "pipeline.report_tasks"],
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
        "pipeline.report_tasks.generate_report": {"queue": "ingest"},
    },
)


@after_setup_logger.connect
def _configure_celery_logging(logger, *args, **kwargs):
    import logging

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for handler in logger.handlers:
        handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
