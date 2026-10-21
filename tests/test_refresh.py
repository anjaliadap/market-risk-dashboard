import pandas as pd
from sqlalchemy import create_engine

from src import refresh
from src.database import store


def test_failure_retains_data(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "refresh.db"))
    monkeypatch.setattr(store, "engine", engine)
    monkeypatch.setattr(refresh, "engine", engine)
    store.initialize()
    meta = {"id": "DGS10", "url": "https://fred.stlouisfed.org/series/DGS10", "unit": "percent"}
    store.save(meta, pd.Series([4.2], index=pd.to_datetime(["2024-01-02"])))

    def fail(*args, **kwargs):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(refresh.FredProvider, "get_history", fail)
    assert not refresh.refresh_one("DGS10")
    assert store.history("DGS10").value.iloc[-1] == 4.2
    assert not refresh.due("DGS10")
