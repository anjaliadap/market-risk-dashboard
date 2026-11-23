"""Workbook profile isolation and local save safety use synthetic data only."""

import hashlib
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from src import excel_sync, process_sync
from src.database import store
from src.settings import Settings, settings


@pytest.fixture
def process_provider(monkeypatch):
    """Stub the lazily imported provider, independently testing persistence boundaries."""
    module = ModuleType("src.providers.process_workbook")
    calls = []

    class Provider:
        def __init__(self, path):
            self.path = Path(path)

        def read(self):
            blob = self.path.read_bytes()
            if blob == b"partial":
                raise ValueError("Incomplete saved workbook")
            return {
                "sha256": hashlib.sha256(blob).hexdigest(),
                "mapping_sha256": "synthetic-profile-v1",
                "metric_count": 1,
                "value": None if blob == b"missing" else len(blob),
                "sections": {},
            }

    def validate(previous, current):
        calls.append((previous, current))
        if previous and previous["value"] is not None and current["value"] is None:
            raise ValueError("Lost valid Process saved value")

    module.ProcessWorkbookProvider = Provider
    module.validate_process_continuity = validate
    monkeypatch.setitem(sys.modules, "src.providers.process_workbook", module)
    return calls


def test_profile_latest_success_and_failure_are_isolated(tmp_path, process_provider):
    with Session(store.engine) as session, session.begin():
        legacy = store.WorkbookImport(
            imported_at=datetime.now(UTC),
            path="synthetic-legacy.xlsx",
            sha256="synthetic-legacy",
            status="success",
            payload=json.dumps({"sections": {"Legacy": {}}, "mapping_sha256": "legacy-v1"}),
        )
        session.add(legacy)
    legacy_id = excel_sync.latest_import(True)["id"]
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(b"saved")
    assert excel_sync.import_workbook(path, profile="process") == "success"
    current = excel_sync.latest_import(True, profile="process")
    assert current["profile"] == "process"
    assert excel_sync.latest_import(True)["id"] == legacy_id
    assert process_provider[0][0] is None
    assert excel_sync.import_workbook(path, profile="process") == "unchanged"
    path.write_bytes(b"missing")
    assert excel_sync.import_workbook(path, profile="process") == "failed"
    assert "Lost valid Process" in excel_sync.latest_import(profile="process")["error"]
    assert excel_sync.latest_import(True, profile="process")["id"] == current["id"]
    assert excel_sync.latest_import()["id"] == legacy_id
    path.write_bytes(b"partial")
    assert excel_sync.import_workbook(path, profile="process") == "failed"
    assert excel_sync.latest_import(True, profile="process")["id"] == current["id"]


def test_process_rechecks_source_after_validation(tmp_path, process_provider, monkeypatch):
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(b"saved")
    assert excel_sync.import_workbook(path, profile="process") == "success"
    valid = excel_sync.latest_import(True, profile="process")["id"]
    provider = sys.modules["src.providers.process_workbook"].ProcessWorkbookProvider
    original = provider.read

    def changed_after_read(instance):
        snapshot = original(instance)
        path.write_bytes(b"changed-during-read")
        return snapshot

    monkeypatch.setattr(provider, "read", changed_after_read)
    assert excel_sync.import_workbook(path, force=True, profile="process") == "failed"
    assert "changed during validation" in excel_sync.latest_import(profile="process")["error"]
    assert excel_sync.latest_import(True, profile="process")["id"] == valid


def test_process_cannot_use_legacy_mapping(tmp_path, process_provider):
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(b"saved")
    assert excel_sync.import_workbook(path, mapping={}, profile="process") == "failed"
    assert "own validated workbook layout" in excel_sync.latest_import(profile="process")["error"]
    with pytest.raises(ValueError, match="Unknown workbook profile"):
        excel_sync.import_workbook(path, profile="unknown")


def test_shared_workbook_settings_prefer_the_standard_path(monkeypatch):
    monkeypatch.setenv("PROCESS_WORKBOOK_PATH", "old-process.xlsx")
    monkeypatch.setenv("EXCEL_WORKBOOK_PATH", "master.xlsx")
    assert Settings(_env_file=None).excel_workbook_path == "master.xlsx"
    monkeypatch.delenv("EXCEL_WORKBOOK_PATH")
    assert Settings(_env_file=None).excel_workbook_path == "old-process.xlsx"


def test_process_poll_settles_hashes_and_keeps_legacy_state_separate(tmp_path, monkeypatch):
    import src.providers.process_workbook as provider

    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(b"first")
    monkeypatch.setattr(settings, "excel_workbook_path", str(path))
    monkeypatch.setattr(settings, "excel_settle_seconds", 5)
    monkeypatch.setattr(process_sync, "_candidate", None)
    monkeypatch.setattr(process_sync, "_future", None)
    monkeypatch.setattr(process_sync, "_attempted", None)
    monkeypatch.setattr(process_sync, "_force_requested", False)
    now = [0.0]
    monkeypatch.setattr(process_sync.time, "monotonic", lambda: now[0])
    mapping = {"version": 1}
    monkeypatch.setattr(provider, "load_process_mapping", lambda: mapping)
    legacy_candidate = excel_sync._candidate
    submitted = []

    class Pool:
        def submit(self, function, source, **kwargs):
            submitted.append((source.read_bytes(), kwargs))

    monkeypatch.setattr(process_sync, "_pool", Pool())
    assert "waiting" in process_sync.poll_workbook(force=True).lower()
    now[0] = 4
    process_sync.poll_workbook()
    assert not submitted
    now[0] = 6
    process_sync.poll_workbook()
    assert submitted == [(b"first", {"force": True, "profile": "process"})]
    stat = path.stat()
    path.write_bytes(b"other")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    process_sync.poll_workbook()
    assert submitted[-1] == (b"other", {"force": False, "profile": "process"})
    count = len(submitted)
    process_sync.poll_workbook()
    assert len(submitted) == count
    mapping["version"] = 2
    process_sync.poll_workbook()
    assert len(submitted) == count + 1  # A mapping update revalidates unchanged source bytes.
    assert excel_sync._candidate == legacy_candidate


def test_process_cli_import_uses_process_profile(tmp_path, process_provider):
    path = tmp_path / "synthetic.xlsx"
    path.write_bytes(b"saved")
    assert process_sync.wait_and_import(path, settle_seconds=0) == "success"
    assert excel_sync.latest_import(True, profile="process")
    assert excel_sync.latest_import(True) is None


def test_process_poll_recognizes_already_imported_workbook(tmp_path, monkeypatch):
    from src.providers import process_workbook

    path = tmp_path / "master.xlsx"
    blob = b"saved workbook"
    path.write_bytes(blob)
    mapping = {"version": 1}
    monkeypatch.setattr(process_workbook, "load_process_mapping", lambda: mapping)
    monkeypatch.setattr(settings, "excel_workbook_path", str(path))
    monkeypatch.setattr(process_sync, "_candidate", None)
    monkeypatch.setattr(process_sync, "_candidate_since", 0.0)
    monkeypatch.setattr(process_sync, "_future", None)
    monkeypatch.setattr(process_sync, "_attempted", None)
    monkeypatch.setattr(process_sync, "_force_requested", False)
    monkeypatch.setattr(process_sync, "_message", "")
    with Session(store.engine) as session, session.begin():
        session.add(
            store.WorkbookImport(
                imported_at=datetime.now(UTC),
                profile="process",
                path=str(path.resolve()),
                sha256=hashlib.sha256(blob).hexdigest(),
                status="success",
                payload=json.dumps(
                    {"mapping_sha256": hashlib.sha256(json.dumps(mapping).encode()).hexdigest()}
                ),
            )
        )

    assert process_sync.poll_workbook() == "Showing the latest saved workbook values"
    assert process_sync._future is None


def test_profile_migration_backfills_existing_rows_and_is_idempotent(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "old-schema.db"))
    migration_path = (
        Path(__file__).resolve().parents[1] / "migrations/versions/0003_workbook_profiles.py"
    )
    spec = importlib.util.spec_from_file_location("synthetic_profile_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE workbook_imports (id INTEGER PRIMARY KEY, payload TEXT)")
        )
        connection.execute(
            text("INSERT INTO workbook_imports (payload) VALUES (:payload)"),
            {"payload": "synthetic-existing-snapshot"},
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(text("SELECT profile, payload FROM workbook_imports")).one()
        assert row == ("legacy", "synthetic-existing-snapshot")
        assert "ix_workbook_imports_profile" in {
            index["name"] for index in inspect(connection).get_indexes("workbook_imports")
        }
    engine.dispose()
