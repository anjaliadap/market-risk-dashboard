"""Local save detection and atomic snapshot publication; no remote access or upload."""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import store
from src.providers.excel import ExcelWorkbookProvider, load_mapping
from src.settings import settings

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="excel-import")
_lock = Lock()
_future = None
_candidate = None
_candidate_since = 0.0
_attempted = None
_message = "Waiting for a stable saved workbook"
_force_requested = False


@lru_cache(maxsize=2)
def _decode_snapshot(payload):
    """Immutable snapshot payloads are shared read-only across UI reruns."""
    return json.loads(payload)


PUBLISHED = ("success", "partial")  # Import statuses that carry a usable snapshot.


def latest_import(success_only=False):
    """Latest import attempt; with ``success_only``, the latest published (usable) snapshot."""
    with Session(store.engine) as session:
        query = select(store.WorkbookImport).order_by(store.WorkbookImport.id.desc())
        if success_only:
            query = query.where(store.WorkbookImport.status.in_(PUBLISHED))
        row = session.scalar(query.limit(1))
        if row is None:
            return None
        return {
            "id": row.id,
            "time": row.imported_at.isoformat(),
            "path": row.path,
            "sha256": row.sha256,
            "status": row.status,
            "error": row.error,
            "snapshot": _decode_snapshot(row.payload) if row.payload else None,
        }


def workbook_file_status():
    if not settings.excel_workbook_path:
        return {"modified_at": None, "error": "Not configured"}
    try:
        stat = Path(settings.excel_workbook_path).expanduser().stat()
        return {
            "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            "error": None,
        }
    except OSError as exc:
        return {"modified_at": None, "error": str(exc)}


def section_continuity_error(name, old_section, new_section):
    """Why ``new_section`` loses a previously valid mapped value, or None if it keeps them all."""
    if new_section is None:
        return f"Missing previously imported section: {name}"
    series = {s["id"]: s for c in new_section["charts"] for s in c["series"]}
    for chart in old_section["charts"]:
        for old in chart["series"]:
            if old.get("role") == "reported_marker":
                continue  # Presentation marker intentionally moves each reported quarter.
            if old["id"] not in series:
                return f"Missing previously imported metric: {old['id']}"
            new = {p["date"]: p["value"] for p in series[old["id"]]["points"]}
            for point in old["points"]:
                if point["value"] is not None and new.get(point["date"]) is None:
                    return f"Lost valid saved value: {old['id']} {point['date']}"
    cells = {
        (t["id"], c["cell"]): c["value"]
        for t in new_section["tables"]
        for row in t["rows"]
        for c in row
    }
    for table in old_section["tables"]:
        for row in table["rows"]:
            for cell in row:
                if cell["value"] is not None and cells.get((table["id"], cell["cell"])) is None:
                    return f"Lost valid table value: {name} {cell['cell']}"
    return None


def validate_continuity(previous, current):
    """Reject loss of a previously valid mapped value, never publish an incomplete save."""
    if not previous:
        return
    for name, old_section in previous["sections"].items():
        error = section_continuity_error(name, old_section, current["sections"].get(name))
        if error:
            raise ValueError(error)


def merge_with_previous(previous, snapshot, previous_time):
    """Per-section publication: keep each section's last valid data when its tab is rejected.

    A section that fails validation, or would lose a previously valid value, is not published from
    this save. If an earlier import had it, that data is carried forward and listed under
    ``retained_sections`` with the reason and the import it came from. Returns the number of
    sections that were imported fresh from this save.
    """
    rejected = snapshot.setdefault("rejected_sections", {})
    retained = snapshot["retained_sections"] = {}
    old_sections = previous["sections"] if previous else {}
    old_retained = previous.get("retained_sections", {}) if previous else {}
    for name in list(snapshot["sections"]):
        if name in old_sections:
            error = section_continuity_error(name, old_sections[name], snapshot["sections"][name])
            if error:
                rejected[name] = error
                del snapshot["sections"][name]
    fresh = len(snapshot["sections"])
    for name, old_section in old_sections.items():
        if name not in rejected:
            continue  # Imported fresh, or no longer mapped (then it is dropped).
        snapshot["sections"][name] = old_section
        since = old_retained.get(name, {}).get("imported_at", previous_time)
        retained[name] = {"reason": rejected[name], "imported_at": since}
    return fresh


def section_state(title, saved=None):
    """How the active snapshot covers one section: imported, retained, rejected or missing."""
    saved = saved if saved is not None else latest_import(success_only=True)
    snapshot = (saved or {}).get("snapshot") or {}
    retained = snapshot.get("retained_sections", {})
    if title in retained:
        return {"state": "retained", **retained[title]}
    if title in snapshot.get("sections", {}):
        return {"state": "imported", "reason": None, "imported_at": saved["time"]}
    reason = snapshot.get("rejected_sections", {}).get(title)
    if reason is None:
        latest = latest_import()
        if latest and latest["status"] == "failed" and latest["error"]:
            reason = latest["error"]
    return {"state": "rejected" if reason else "missing", "reason": reason, "imported_at": None}


def import_workbook(path, mapping=None, force=False):
    """Validate each section before one short transaction publishes a new active snapshot.

    Sections that pass are published; sections that fail keep their last valid data (or stay
    unavailable). Status is "success" when every mapped section passed, "partial" when some were
    rejected, and "failed" when nothing new could be published.
    """
    source = str(Path(path).expanduser().resolve())
    digest = None
    try:
        snapshot = ExcelWorkbookProvider(source, mapping).read()
        digest = snapshot["sha256"]
        previous = latest_import(success_only=True)
        if (
            previous
            and not force
            and previous["sha256"] == digest
            and previous["snapshot"].get("mapping_sha256") == snapshot["mapping_sha256"]
            and previous["snapshot"].get("schema") == snapshot.get("schema")
        ):
            return "unchanged"
        fresh = merge_with_previous(
            previous["snapshot"] if previous else None,
            snapshot,
            previous["time"] if previous else None,
        )
        rejected = snapshot["rejected_sections"]
        if not fresh:
            raise ValueError("; ".join(f"{name}: {reason}" for name, reason in rejected.items()))
        if hashlib.sha256(Path(source).read_bytes()).hexdigest() != digest:
            raise ValueError("Workbook changed during validation; prior snapshot retained")
        status = "partial" if rejected else "success"
        summary = "; ".join(f"{name}: {reason}" for name, reason in rejected.items())
        payload = json.dumps(snapshot, allow_nan=False, separators=(",", ":"))
        with Session(store.engine) as session, session.begin():
            session.add(
                store.WorkbookImport(
                    imported_at=datetime.now(UTC),
                    path=source,
                    sha256=digest,
                    status=status,
                    error=("Rejected sections: " + summary)[:2000] if rejected else None,
                    payload=payload,
                )
            )
        logger.info(
            "Excel import %s sha256=%s metrics=%s rejected=%s",
            status,
            digest,
            snapshot["metric_count"],
            sorted(rejected),
        )
        return status
    except Exception as exc:
        logger.exception("Excel import failed; prior valid snapshot retained")
        with Session(store.engine) as session, session.begin():
            session.add(
                store.WorkbookImport(
                    imported_at=datetime.now(UTC),
                    path=source,
                    sha256=digest,
                    status="failed",
                    error=str(exc)[:2000],
                )
            )
        return "failed"


def poll_workbook(force=False):
    """Nonblocking UI poll. Two unchanged stat observations, then stable byte/hash read.

    Hash content on each settled poll so mtime/filename alone never defines a version.
    A force request still honors the save-settling window.
    """
    global _future, _candidate, _candidate_since, _attempted, _message, _force_requested
    path = settings.excel_workbook_path
    if not path:
        return "Workbook not configured (EXCEL_WORKBOOK_PATH)"
    with _lock:
        _force_requested = _force_requested or force
        if _future is not None and not _future.done():
            return "Validating saved workbook in background"
        if _future is not None:
            try:
                result = _future.result()
                if result == "partial":
                    rejected = (latest_import(success_only=True) or {}).get("snapshot") or {}
                    names = ", ".join(sorted(rejected.get("rejected_sections", {})))
                    _message = (
                        f"Import partial; sections not updated: {names} (see Workbook "
                        "Administration). Bloomberg refresh time remains unknown"
                    )
                else:
                    _message = "Import " + result + "; Bloomberg refresh time remains unknown"
            except Exception as exc:
                logger.exception("Workbook worker failed")
                _message = f"Import worker failed; prior snapshot retained: {exc}"
            _future = None
        try:
            p = Path(path).expanduser().resolve()
            stat = p.stat()
            identity = (str(p), stat.st_size, stat.st_mtime_ns)
            if identity != _candidate:
                _candidate = identity
                _candidate_since = time.monotonic()
                _message = "Save detected; waiting for file writes to settle"
                return _message
            if time.monotonic() - _candidate_since < settings.excel_settle_seconds:
                return "Waiting for file writes to settle"
            blob = p.read_bytes()
            after = p.stat()
            if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                _candidate = None
                return "Workbook changed during save; waiting"
            digest = hashlib.sha256(blob).hexdigest()
            mapping_digest = hashlib.sha256(
                json.dumps(load_mapping(), sort_keys=True).encode()
            ).hexdigest()
            version = (str(p), digest, mapping_digest)
            if version != _attempted or _force_requested:
                _attempted = version
                _future = _pool.submit(import_workbook, p, force=_force_requested)
                _force_requested = False
                return "Validating saved workbook in background"
        except OSError as exc:
            _message = f"Workbook unavailable; last valid snapshot retained: {exc}"
        return _message


def wait_and_import(path, settle_seconds=None, force=False):
    """CLI: stable stats before importing. Bounds waiting; source read also verifies stability."""
    delay = settings.excel_settle_seconds if settle_seconds is None else settle_seconds
    p = Path(path)
    before = p.stat()
    time.sleep(max(0, delay))
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Workbook is still being written; retry after Excel saves")
    return import_workbook(p, force=force)
