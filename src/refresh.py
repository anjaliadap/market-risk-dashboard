import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.store import Job, engine, save
from src.providers.fred import FredProvider
from src.registry import BY_ID

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=1)
_lock = Lock()
_pending = set()


def refresh_one(series_id):
    try:
        count = save(BY_ID[series_id], FredProvider().get_history(series_id))
        logger.info("refresh success series=%s new_versions=%s", series_id, count)
        return True
    except Exception as exc:
        logger.exception("refresh failed series=%s", series_id)
        with Session(engine) as session, session.begin():
            session.add(
                Job(
                    series_id=series_id,
                    started_at=datetime.now(UTC),
                    status="failed",
                    error=str(exc)[:1800],
                )
            )
        return False


def due(series_id):
    with Session(engine) as session:
        job = session.scalar(
            select(Job).where(Job.series_id == series_id).order_by(Job.started_at.desc()).limit(1)
        )
        # Retry failed requests at most once per hour; successful retrieval once per day.
        return job is None or datetime.now(UTC) - job.started_at.replace(tzinfo=UTC) > timedelta(
            hours=1 if job.status == "failed" else 24
        )


def enqueue(ids):
    for series_id in ids:
        with _lock:
            if series_id in _pending or not due(series_id):
                continue
            _pending.add(series_id)

        def work(key=series_id):
            try:
                refresh_one(key)
            finally:
                with _lock:
                    _pending.discard(key)

        _pool.submit(work)
