import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.database import store


def test_revisions_and_dedup(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "engine", create_engine("sqlite:///" + str(tmp_path / "test.db")))
    store.initialize()
    meta = {"id": "X", "url": "https://example.org", "unit": "percent"}
    s = pd.Series([1.0], index=pd.to_datetime(["2024-01-01"]))
    assert store.save(meta, s) == 1
    assert store.save(meta, s) == 0
    s.iloc[0] = 2
    assert store.save(meta, s) == 1
    assert store.history("X").value.iloc[0] == 2
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(store.Observation)) == 2
