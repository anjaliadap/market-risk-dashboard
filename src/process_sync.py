"""Independent local watcher for the latest Process workbook sections; no network access."""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from src.excel_sync import import_workbook
from src.settings import settings

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="process-workbook-import")
_lock = Lock()
_future = None
_candidate = None
_candidate_since = 0.0
_attempted = None
_message = "Waiting for a stable saved workbook"
_force_requested = False


def poll_workbook(force=False):
    """Settle file writes before a bounded, atomic Process-profile import.

    Polling state and the worker are separate from legacy Excel synchronization.
    A failed new save leaves the latest valid Process snapshot available.
    """
    global _future, _candidate, _candidate_since, _attempted, _message, _force_requested
    path = settings.excel_workbook_path
    if not path:
        return "Workbook not configured (EXCEL_WORKBOOK_PATH)"
    with _lock:
        _force_requested = _force_requested or force
        if _future is not None and not _future.done():
            return "Validating saved Process workbook in background"
        if _future is not None:
            try:
                _message = "Process import " + _future.result() + "; source refresh time unknown"
            except Exception as exc:
                logger.exception("Process workbook worker failed")
                _message = f"Process import worker failed; prior snapshot retained: {exc}"
            _future = None
        try:
            source = Path(path).expanduser().resolve()
            stat = source.stat()
            identity = (str(source), stat.st_size, stat.st_mtime_ns)
            if identity != _candidate:
                _candidate = identity
                _candidate_since = time.monotonic()
                _message = "Save detected; waiting for file writes to settle"
                return _message
            if time.monotonic() - _candidate_since < settings.excel_settle_seconds:
                return "Waiting for file writes to settle"
            blob = source.read_bytes()
            after = source.stat()
            if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                _candidate = None
                return "Workbook changed during save; waiting"
            from src.providers.process_workbook import load_process_mapping

            mapping_digest = hashlib.sha256(
                json.dumps(load_process_mapping(), sort_keys=True).encode()
            ).hexdigest()
            version = (str(source), hashlib.sha256(blob).hexdigest(), mapping_digest)
            if version != _attempted or _force_requested:
                _attempted = version
                _future = _pool.submit(
                    import_workbook, source, force=_force_requested, profile="process"
                )
                _force_requested = False
                return "Validating saved Process workbook in background"
        except (OSError, ValueError) as exc:
            _message = f"Process workbook unavailable; last valid snapshot retained: {exc}"
        return _message


def wait_and_import(path, settle_seconds=None, force=False):
    """CLI import after stable file stats; the provider verifies stable bytes again."""
    delay = settings.excel_settle_seconds if settle_seconds is None else settle_seconds
    source = Path(path).expanduser()
    before = source.stat()
    time.sleep(max(0, delay))
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Workbook is still being written; retry after Excel saves")
    return import_workbook(source, force=force, profile="process")
