"""A survey snapshot either updates all related fields or preserves them all."""

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from src import refresh
from src.database import store
from src.providers.aaii import AaiiProvider
from src.providers.workbook_sections import AAII_IDS

REAL_ENQUEUE = refresh.enqueue


@pytest.fixture
def survey_database(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "survey.db"))
    monkeypatch.setattr(store, "engine", engine)
    monkeypatch.setattr(refresh, "engine", engine)
    metadata = {
        key: {
            "id": key,
            "url": "https://www.aaii.com/files/surveys/sentiment.xls",
            "unit": "index points" if key.endswith("CLOSE") else "percent",
            "min_value": 0,
        }
        for key in AAII_IDS
    }
    monkeypatch.setattr(refresh, "BY_ID", metadata)
    store.initialize()
    frame = pd.DataFrame(
        [[36.0, 20.0, 44.0, 5000.0]],
        index=pd.to_datetime(["2024-01-04"]),
        columns=AAII_IDS,
    )
    store.save_many([(metadata[key], frame[key]) for key in AAII_IDS])
    yield frame
    engine.dispose()


def observation_count():
    with Session(store.engine) as session:
        return session.scalar(select(func.count()).select_from(store.Observation))


def latest_jobs():
    with Session(store.engine) as session:
        rows = session.scalars(select(store.Job).order_by(store.Job.id)).all()
        return {row.series_id: row.status for row in rows}


def test_requesting_any_survey_field_refreshes_one_snapshot_and_every_group_field(
    survey_database, monkeypatch
):
    next_frame = pd.DataFrame(
        [[40, 18, 42, 5100]], index=pd.to_datetime(["2024-01-11"]), columns=AAII_IDS
    )
    calls = []

    def source_snapshot(self):
        calls.append(1)
        return next_frame

    monkeypatch.setattr(AaiiProvider, "get_frame", source_snapshot)
    assert refresh.refresh_one("AAII_BEARISH")
    assert len(calls) == 1
    for key in AAII_IDS:
        history = store.history(key)
        assert len(history) == 2
        assert history.index[-1] == pd.Timestamp("2024-01-11")
        assert history.value.iloc[-1] == next_frame[key].iloc[0]
    assert observation_count() == 8
    assert set(latest_jobs().values()) == {"success"}


@pytest.mark.parametrize("invalid_field", AAII_IDS)
def test_one_invalid_input_retains_all_previous_survey_fields(
    survey_database, monkeypatch, invalid_field
):
    revised = survey_database.copy()
    revised.iloc[0] = [40, 18, 42, 5100]
    revised.loc[:, invalid_field] = np.inf
    monkeypatch.setattr(AaiiProvider, "get_frame", lambda self: revised)
    assert not refresh.refresh_one("AAII_NEUTRAL")
    assert observation_count() == 4
    for key in AAII_IDS:
        assert store.history(key).value.tolist() == survey_database[key].tolist()
    assert set(latest_jobs()) == set(AAII_IDS)
    assert set(latest_jobs().values()) == {"failed"}
    assert not refresh.due("AAII_BULLISH")


def test_missing_source_component_rejects_whole_survey_group(survey_database, monkeypatch):
    incomplete = survey_database.drop(columns=["AAII_SP500_WEEKLY_CLOSE"])
    monkeypatch.setattr(AaiiProvider, "get_frame", lambda self: incomplete)
    assert not refresh.refresh_one("AAII_BULLISH")
    assert observation_count() == 4
    assert set(latest_jobs().values()) == {"failed"}


def test_database_failure_rolls_back_all_new_group_versions(survey_database, monkeypatch):
    revised = survey_database.copy()
    revised.iloc[0] = [40, 18, 42, 5100]
    monkeypatch.setattr(AaiiProvider, "get_frame", lambda self: revised)

    def simulated_database_error(mapper, connection, target):
        if target.series_id == "AAII_SP500_WEEKLY_CLOSE":
            raise RuntimeError("simulated database failure during final group insert")

    event.listen(store.Observation, "before_insert", simulated_database_error)
    try:
        assert not refresh.refresh_one("AAII_BULLISH")
    finally:
        event.remove(store.Observation, "before_insert", simulated_database_error)
    assert observation_count() == 4
    for key in AAII_IDS:
        assert store.history(key).value.tolist() == survey_database[key].tolist()
    assert set(latest_jobs().values()) == {"failed"}


def test_enqueue_deduplicates_related_survey_refreshes(monkeypatch):
    submitted = []

    class RecordingPool:
        def submit(self, work):
            submitted.append(work)

    monkeypatch.setattr(refresh, "_pool", RecordingPool())
    # The autouse isolation fixture disables background work for page tests.
    # Restore scheduling here so this test exercises the actual group logic.
    monkeypatch.setattr(refresh, "enqueue", REAL_ENQUEUE)
    monkeypatch.setattr(refresh, "_pending", set())
    monkeypatch.setattr(refresh, "due", lambda key: True)
    refresh.enqueue(list(AAII_IDS))
    assert len(submitted) == 1
    assert refresh._pending == {"AAII_BULLISH"}
