"""Page renders for Recession, VIX & Options, Demand, Financing and Supply.

All observations and workbook snapshots below are synthetic and exist only in an isolated
temporary database.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from dashboard.sections import demand, financing, recession, supply, vix_options

ROOT = Path(__file__).resolve().parents[1]
FREQ = {"daily": "B", "weekly": "W-FRI", "monthly": "MS", "quarterly": "QS", "annual": "YS"}
SCRIPT = """from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace = runpy.run_path({path!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""
PAGES = {
    "Recession": recession,
    "VIX & Options": vix_options,
    "Demand": demand,
    "Financing": financing,
    "Supply": supply,
}


@pytest.fixture
def database(monkeypatch, tmp_path):
    from src.database import store

    engine = create_engine("sqlite:///" + str(tmp_path / "fixtures.db"))
    monkeypatch.setattr(store, "engine", engine)
    store.initialize()
    return store


def seed_observations(store, ids):
    from src.registry import BY_ID

    rng = np.random.default_rng(11)
    for key in ids:
        meta = BY_ID[key]
        index = pd.date_range("2000-01-01", "2025-06-30", freq=FREQ[meta["frequency"]])
        if key == "USREC":
            values = pd.Series(0.0, index=index)
            values.loc["2008-01-01":"2009-06-01"] = 1.0
        else:
            walk = np.cumsum(rng.normal(0.002, 0.01, len(index)))
            values = pd.Series(5 * np.exp(walk), index=index)
        store.save(meta, values)


def synthetic_snapshot():
    """Snapshot following the real mapping contract, with synthetic values."""
    from src.providers.excel import load_mapping

    rng = np.random.default_rng(3)
    sections = {}
    for title in ("Recession", "VIX & Options", "Demand", "Financing"):
        config = load_mapping()["sections"][title]
        charts = []
        for chart in config["charts"]:
            out = {"id": chart["id"], "title": chart["title"], "series": []}
            for spec in chart["series"]:
                quarterly = bool(spec.get("period_labels_row"))
                dates = pd.date_range(
                    "2021-03-31" if quarterly else "2020-01-03",
                    periods=20 if quarterly else 80,
                    freq="QE" if quarterly else "W-FRI",
                )
                reported = dates[:16] if quarterly else dates
                points = []
                for i, d in enumerate(dates):
                    forward = quarterly and d not in reported
                    value = None if spec["role"] == "reported_marker" else float(0.5 + rng.random())
                    points.append(
                        {
                            "date": d.date().isoformat(),
                            "value": value,
                            "cell": f"Z{i + 3}",
                            "forward": forward,
                            "formula": None,
                        }
                    )
                out["series"].append(
                    {
                        **spec,
                        "points": points,
                        "latest_reported": reported[-1].date().isoformat() if quarterly else None,
                    }
                )
            charts.append(out)
        tables = []
        for table in config["tables"]:
            rows = []
            for r in range(4, 54):
                row = []
                for col in "BCDEFGH":
                    value = None
                    if col == "B" and r in recession_rows():
                        value = recession_rows()[r]
                    if col == "F" and r in recession_rows():
                        value = "Saved status"
                    licensed = ("Leading economic indicators (Y/Y)", "Composite PMI")
                    if col == "G" and recession_rows().get(r) in licensed:
                        value = 1
                    row.append(
                        {
                            "cell": f"{col}{r}",
                            "value": value,
                            "format": "General",
                            "formula": False,
                            "font_color": None,
                        }
                    )
                rows.append(row)
            tables.append({**table, "rows": rows, "as_of": None})
        sections[title] = {"notes": config["notes"], "charts": charts, "tables": tables}
    return {
        "sections": sections,
        "metric_count": 1,
        "latest_observation": "2025-06-30",
        "diagnostics": {},
        "issues": [],
    }


def recession_rows():
    from src.analytics.signals import RECESSION_ROWS

    return {row: metric for metric, row in RECESSION_ROWS.items()}


def seed_snapshot(store):
    with Session(store.engine) as session, session.begin():
        session.add(
            store.WorkbookImport(
                imported_at=datetime.now(UTC),
                path="synthetic.xlsx",
                sha256="0" * 64,
                status="success",
                payload=json.dumps(synthetic_snapshot()),
            )
        )


def checklist_frame(app):
    """The first rule-based checklist table (identified by its columns, not position)."""
    for element in app.dataframe:
        frame = element.value.data if hasattr(element.value, "data") else element.value
        if {"Metric", "Signal", "Rule"} <= set(frame.columns):
            return frame
    raise AssertionError("No checklist table rendered")


def run(title):
    return AppTest.from_string(SCRIPT.format(path=str(ROOT / "dashboard/app.py"), title=title)).run(
        timeout=120
    )


@pytest.mark.parametrize(
    "title,charts",
    [("Recession", 9), ("VIX & Options", 4), ("Demand", 6), ("Financing", 4), ("Supply", 3)],
)
def test_page_with_observations(title, charts, database):
    module = PAGES[title]
    seed_observations(database, module.IDS)
    app = run(title)
    assert not app.exception
    assert app.title[0].value == title
    assert len(app.tabs) == 4
    assert len(app.get("plotly_chart")) >= charts
    labels = {m.label: m.value for m in app.metric}
    assert any(label.startswith("Red ") for label in labels)
    assert all(labels[k.label] != "—" for k in module.KPIS)


@pytest.mark.parametrize("title", list(PAGES))
def test_page_without_observations(title, database):
    app = run(title)
    assert not app.exception
    assert any("UNAVAILABLE" in w.value for w in app.warning)
    coverage = next(m.value for m in app.metric if m.label == "Coverage")
    assert coverage.startswith("0 of")  # nothing evaluated, nothing assumed green


@pytest.mark.parametrize("title", ["Recession", "VIX & Options", "Demand", "Financing"])
def test_page_with_workbook_snapshot(title, database):
    seed_observations(database, PAGES[title].IDS)
    seed_snapshot(database)
    app = run(title)
    assert not app.exception
    # The sponsor workbook tab leads when a validated snapshot exists.
    assert app.tabs[0].label == "Sponsor workbook"
    assert not any("No validated workbook snapshot" in i.value for i in app.info)


def test_recession_uses_saved_flags_only_for_licensed_items(database):
    seed_observations(database, recession.IDS)
    seed_snapshot(database)
    app = run("Recession")
    frame = checklist_frame(app)
    licensed = frame.set_index("Metric").loc[["Leading economic indicators (Y/Y)", "Composite PMI"]]
    assert (licensed["Source"] == "Workbook (saved manual flag)").all()
    assert (licensed["Signal"] == "RED").all()
    assert {"Workbook status", "Workbook flag"} <= set(frame.columns)
    assert frame.set_index("Metric").loc["Industrial production (Y/Y)", "Source"].startswith("FRED")


def test_demand_and_financing_trackers_use_workbook(database):
    seed_snapshot(database)
    for title, metric in (
        ("Demand", "Slowing AI sales growth vs capex growth"),
        ("Financing", "Hyperscaler capex > CFOps"),
    ):
        app = run(title)
        assert not app.exception
        tracker = checklist_frame(app)
        row = tracker.set_index("Metric").loc[metric]
        assert row["Signal"] in {"RED", "Not red"}
        assert row["Source"].startswith("Workbook")


def test_supply_analyst_log_round_trip(database):
    from dashboard.sections.extras import observations, store_observations, validate

    ok, errors = validate(
        "gpu_pricing",
        [
            {
                "date": "2025-05-01",
                "chip": "H100 SXM",
                "pricing_type": "On-demand",
                "provider": "Example cloud",
                "value": 2.49,
                "source_url": "https://example.com/pricing",
            },
            {"date": "2025-05-01", "chip": "H100 SXM", "value": 2.0, "source_url": "nope"},
            {"date": "2999-01-01", "chip": "B200", "value": 5.0, "source_url": "https://x.y"},
        ],
    )
    assert len(ok) == 1 and len(errors) == 2
    store_observations("gpu_pricing", ok)
    stored = observations("gpu_pricing")
    assert stored["value"].tolist() == [2.49]
    assert stored["unit"].iloc[0] == "USD per GPU-hour"
    app = run("Supply")
    assert not app.exception
    assert any("ANALYST-SOURCED" in str(c.proto.spec) for c in app.get("plotly_chart"))


def test_registry_covers_section_ids():
    from src.registry import BY_ID

    for module in PAGES.values():
        assert set(module.IDS) <= BY_ID.keys()
        assert {k.series_id for k in module.KPIS} <= set(module.IDS)
