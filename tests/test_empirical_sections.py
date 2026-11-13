"""Page renders for Momentum, FC Data, Failure Candidates and S&P Relative.

Every value below is synthetic and lives only in an isolated temporary database.
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

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = """from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace = runpy.run_path({path!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""
TITLES = ["Momentum", "FC Data", "Failure Candidates", "S&P Relative"]
DATES = pd.date_range("1990-01-31", "2026-09-30", freq="ME")
SECTORS = [
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Technology",
    "Communications",
    "Utilities",
    "Real Estate",
]


@pytest.fixture
def database(monkeypatch, tmp_path):
    from src.database import store

    engine = create_engine("sqlite:///" + str(tmp_path / "fixtures.db"))
    monkeypatch.setattr(store, "engine", engine)
    store.initialize()
    return store


def synthetic_values(series_id, n, rng):
    t = np.arange(n)
    if series_id == "momentum_0_0":
        return 55 + 18 * np.sin(t / 20) + rng.normal(0, 1, n)  # crosses 70 several times
    if series_id == "momentum_0_1":
        return np.full(n, 55.0)
    if series_id == "momentum_0_2":
        return np.full(n, 70.0)
    if series_id.startswith("fc_data") and series_id.endswith("_1"):
        values = np.zeros(n)
        values[(DATES[:n] >= "2008-01-31") & (DATES[:n] <= "2009-06-30")] = 1
        return values
    if series_id.startswith("fc_data"):
        return np.clip(0.15 + 0.05 * np.sin(t / 15 + rng.random() * 6), 0, 1)
    if series_id == "sandp_relative_2_0":
        return 300 * 1.007**t
    if series_id == "sandp_relative_2_1":
        return 400 * 1.005**t
    if series_id == "sandp_relative_2_2":
        return 20 * 1.004**t
    if series_id in ("sandp_relative_0_0", "sandp_relative_0_2"):
        return 300 * 1.007**t / (400 * 1.005**t)
    if series_id == "sandp_relative_0_1":
        return pd.Series(300 * 1.007**t / (400 * 1.005**t)).rolling(84).mean().to_numpy()
    if series_id in ("sandp_relative_1_0", "sandp_relative_1_2"):
        return 300 * 1.007**t / (20 * 1.004**t)
    if series_id == "sandp_relative_1_1":
        return pd.Series(300 * 1.007**t / (20 * 1.004**t)).rolling(84).mean().to_numpy()
    return rng.random(n)


def cell(coordinate, value):
    return {
        "cell": coordinate,
        "value": value,
        "format": "General",
        "formula": False,
        "font_color": None,
    }


def failure_rows(fc_series):
    """Failure Candidates!AC5:AS20 consistent with the synthetic FC Data history."""
    labels = SECTORS + [None, "Big Growers", "Expensive", None, "Leveraged Borrowers"]
    weights = {"Technology": (0.40, 0.38, 0.30), "Financials": (0.20, 0.05, 0.12)}
    rows = []
    for r, label in zip(range(5, 21), labels, strict=True):
        values = {}
        if label:
            s = fc_series[label]
            z = (s.iloc[-1] - s.mean()) / s.std(ddof=1)
            values.update(
                AC=label, AD=s.iloc[-1], AE=s.mean(), AF=z, AG=0.01, AH=-0.01, AI=0.02, AJ=-0.02
            )
            if label in SECTORS:
                opp, patient, sp = weights.get(label, (0.0, 0.0, 0.03))
                values.update(AK=opp, AL=patient, AM=sp)
                for col, w, out in (("AO", opp, "AR"), ("AP", patient, "AS")):
                    rel = "Overweight" if w > sp else "Underweight"
                    values[col] = rel
                    if rel == "Overweight":
                        values[out] = "Risk" if z > 0 else "Less Risk"
        rows.append(
            [
                cell(f"{c}{r}", values.get(c))
                for c in [
                    "AC",
                    "AD",
                    "AE",
                    "AF",
                    "AG",
                    "AH",
                    "AI",
                    "AJ",
                    "AK",
                    "AL",
                    "AM",
                    "AN",
                    "AO",
                    "AP",
                    "AQ",
                    "AR",
                    "AS",
                ]
            ]
        )
    return rows


def synthetic_snapshot():
    from src.providers.excel import load_mapping

    rng = np.random.default_rng(5)
    mapping = load_mapping()["sections"]
    sections, fc_series = {}, {}
    for title in ("Momentum", "FC Data", "S&P Relative", "Failure Candidates"):
        config = mapping[title]
        charts = []
        for chart in config["charts"]:
            out = {"id": chart["id"], "title": chart["title"], "series": []}
            for spec in chart["series"]:
                values = synthetic_values(spec["id"], len(DATES), rng)
                points = [
                    {
                        "date": d.date().isoformat(),
                        "value": None if np.isnan(v) else float(v),
                        "cell": f"Z{i}",
                        "forward": False,
                        "formula": None,
                    }
                    for i, (d, v) in enumerate(zip(DATES, values, strict=True))
                ]
                if title == "FC Data" and spec["id"].endswith("_0"):
                    fc_series[spec["name"]] = pd.Series(values, index=DATES)
                out["series"].append({**spec, "points": points, "latest_reported": None})
            charts.append(out)
        tables = []
        for table in config["tables"]:
            if table["id"] == "failure_candidates":
                rows = failure_rows(fc_series)
            else:
                rows = [
                    [
                        cell(c, v)
                        for c, v in zip(
                            ["AGJ5", "AGK5", "AGL5", "AGM5"], [0.8, 0.0, -4.4, -2.7], strict=True
                        )
                    ]
                ]
            tables.append({**table, "rows": rows, "as_of": "2026-09-01"})
        sections[title] = {"notes": config["notes"], "charts": charts, "tables": tables}
    return {
        "sections": sections,
        "metric_count": 1,
        "latest_observation": "2026-09-30",
        "diagnostics": {},
        "issues": [],
    }


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


def run(title):
    return AppTest.from_string(SCRIPT.format(path=str(ROOT / "dashboard/app.py"), title=title)).run(
        timeout=120
    )


def frames(app):
    return [d.value.data if hasattr(d.value, "data") else d.value for d in app.dataframe]


@pytest.mark.parametrize(
    "title,charts",
    [("Momentum", 2), ("FC Data", 17), ("Failure Candidates", 2), ("S&P Relative", 6)],
)
def test_page_with_snapshot(title, charts, database):
    seed_snapshot(database)
    app = run(title)
    assert not app.exception
    assert app.title[0].value == title
    assert len(app.tabs) == 4
    assert app.tabs[0].label == "Sponsor workbook"
    assert len(app.get("plotly_chart")) >= charts
    assert not any("UNAVAILABLE · No validated workbook snapshot" in w.value for w in app.warning)


@pytest.mark.parametrize("title", ["Momentum", "FC Data", "Failure Candidates"])
def test_workbook_pages_without_snapshot(title, database):
    app = run(title)
    assert not app.exception
    assert any("UNAVAILABLE" in w.value for w in app.warning)
    assert len(app.get("plotly_chart")) == 0  # nothing is synthesized without saved data


def test_momentum_signal_board_and_study(database):
    seed_snapshot(database)
    app = run("Momentum")
    labels = {m.label: m.value for m in app.metric}
    assert labels["Coverage"] == "3 of 3 evaluated"
    tables = frames(app)
    episodes = next(f for f in tables if "Peak score" in f.columns)
    assert len(episodes) >= 2
    study = next(f for f in tables if "Horizon" in f.columns)
    assert study["Crossings with data"].iloc[0] >= 1


def test_fc_statistics_match_saved_summary(database):
    seed_snapshot(database)
    app = run("FC Data")
    stats = next(f for f in frames(app) if "Matches sponsor" in f.columns)
    assert len(stats) == 14
    assert (stats["Matches sponsor"] == "Yes").all()


def test_failure_candidates_rules_and_exposure(database):
    seed_snapshot(database)
    app = run("Failure Candidates")
    assert not any("Saved flags differ" in w.value for w in app.warning)
    labels = {m.label: m.value for m in app.metric}
    # Technology is overweight in both portfolios; Financials only in OPP.
    assert labels["OPP: sectors at 'Risk'"].endswith("of 2")
    assert labels["Patient: sectors at 'Risk'"].endswith("of 1")


def test_sp_relative_reversion_levels(database):
    seed_snapshot(database)
    app = run("S&P Relative")
    labels = {m.label for m in app.metric}
    assert {"S&P 500 ÷ gold", "S&P 500 ÷ oil"} <= labels
    summary = next(f for f in frames(app) if "S&P 500 implied at 7Yr avg" in f.columns)
    assert summary["S&P 500 implied at 7Yr avg"].notna().all()


def test_navigation_follows_workbook_tab_order():
    pages = json.loads((ROOT / "config/pages.json").read_text())
    order = [t for group in pages.values() for t in group]
    tabs = [
        "Momentum",
        "FC Data",
        "Failure Candidates",
        "Market Data",
        "Bear Market",
        "S&P vs Bonds",
        "Valuation",
        "S&P 500 Fundamentals",
        "Margin Debt",
        "S&P Relative",
        "Gold to Oil",
        "Bull vs Bear",
        "VIX & Options",
        "BTC",
        "Banks",
        "Housing",
        "Energy",
        "Recession",
        "Consumer",
        "Demand",
        "Financing",
    ]
    assert [t for t in order if t in tabs] == tabs
    assert next(iter(pages)) == "Empirical"
