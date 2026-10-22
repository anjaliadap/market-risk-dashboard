"""Tests never ingest company data, access live providers, or write the user's database."""

import pytest
from sqlalchemy import create_engine


@pytest.fixture(autouse=True)
def isolated_services(tmp_path, monkeypatch):
    from src import refresh
    from src.database import store
    from src.settings import settings

    engine = create_engine("sqlite:///" + str(tmp_path / "isolated.db"))
    monkeypatch.setattr(store, "engine", engine)
    monkeypatch.setattr(refresh, "engine", engine)
    monkeypatch.setattr(refresh, "enqueue", lambda ids: None)
    monkeypatch.setattr(settings, "excel_workbook_path", "")
    store.initialize()
    yield
    engine.dispose()
