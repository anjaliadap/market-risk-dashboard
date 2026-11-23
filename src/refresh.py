import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.store import Job, engine, save_many
from src.providers.fred import FredProvider  # noqa: F401 -- retained public import for callers/tests
from src.providers.workbook_sections import fetch_group, group_ids, group_key, validate_history
from src.registry import BY_ID

logger = logging.getLogger(__name__)

_pool = ThreadPoolExecutor(max_workers=1)
_lock = Lock()
_pending = set()


def refresh_one(series_id):
    try:
        frames = fetch_group(series_id)
        inputs = [
            (BY_ID[key], validate_history(frame, BY_ID[key])) for key, frame in frames.items()
        ]
        count = sum(save_many(inputs).values())
        logger.info("refresh success series=%s new_versions=%s", series_id, count)
        return True
    except Exception as exc:
        logger.exception("refresh failed series=%s", series_id)
        with Session(engine) as session, session.begin():
            for key in group_ids(series_id):
                session.add(
                    Job(
                        series_id=key,
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
        minutes = (
            60 if job and job.status == "failed" else BY_ID[series_id].get("refresh_minutes", 1440)
        )
        return job is None or datetime.now(UTC) - job.started_at.replace(tzinfo=UTC) > timedelta(
            minutes=minutes
        )


def enqueue(ids):
    for series_id in ids:
        series_id = group_key(series_id)
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
