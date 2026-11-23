"""Data-source labels: worked out from the data, and switching when the data's origin changes.

Every value is synthetic and lives in an isolated temporary database.
"""

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from src import provenance
from src.database import store
from src.registry import BY_ID

ROOT = Path(__file__).resolve().parents[1]


def test_download_urls_name_the_provider():
    assert provenance.provider_for_url("https://fred.stlouisfed.org/series/DGS10") == "FRED"
    assert provenance.provider_for_url("https://api.bls.gov/publicAPI/v2") == "BLS"
    assert provenance.provider_for_url("https://www.eia.gov/opendata") == "EIA"
    # A site nobody has configured yet is still named, by its host.
    assert provenance.provider_for_url("https://www.example-data.org/x") == "example-data.org"
    assert provenance.provider_for_url("") is None


def test_fred_label_names_the_producer():
    (label,) = provenance.independent_sources("UNRATE", BY_ID["UNRATE"]["url"], BY_ID["UNRATE"])
    assert label["provider"] == "FRED"
    assert label["detail"].startswith("UNRATE")


def test_describe_groups_by_provider():
    text = provenance.describe(
        [
            provenance.source(
                "Bloomberg", "SPX Index PX_LAST", "PCM - Monthly Market & Risk Monitor"
            ),
            provenance.source(
                "Bloomberg", "XAUUSD Curncy PX_LAST", "PCM - Monthly Market & Risk Monitor"
            ),
            provenance.source("FRED", "DGS10"),
            provenance.source("FRED", "DGS10"),  # duplicates collapse
        ]
    )
    assert text == (
        "Bloomberg (SPX Index PX_LAST; XAUUSD Curncy PX_LAST) via PCM - Monthly Market & Risk Monitor · FRED (DGS10)"
    )


def test_carry_labels_combined_series_with_every_input():
    a = provenance.tag(pd.Series([1.0, 2.0]), [provenance.source("FRED", "A")])
    b = provenance.tag(pd.Series([3.0, 4.0]), [provenance.source("Bloomberg", "B")])
    ratio = a / b  # pandas keeps only the left label here...
    assert provenance.providers(provenance.sources_of(ratio)) == ["FRED"]
    provenance.carry(ratio, a, b)  # ...so combined series are relabelled explicitly
    assert provenance.providers(provenance.sources_of(ratio)) == ["FRED", "Bloomberg"]


def traced_workbook():
    book = Workbook()
    data = book.active
    data.title = "Data"
    data["A1"] = "SPX Index"
    data["B2"] = '=BDH("HOMECOMP Index","PX_LAST","2000-01-01","","cols=2;rows=3")'
    data["B3"], data["C3"] = datetime(2000, 1, 31), 125.5  # written by the BDH array
    data["B4"], data["C4"] = datetime(2000, 2, 29), 126.0
    data["E2"] = '=_xll.BDP(A1,"PX_LAST")'  # ticker held in a referenced cell
    data["F2"] = 42  # typed in
    data["G2"] = "=1+1"  # pure calculation
    calc = book.create_sheet("Calc")
    calc["A1"] = "=Data!C3*2"  # traced back to the Bloomberg array
    calc["A2"] = "=Data!F2/Data!E2"  # manual input and Bloomberg
    data["H3"], data["H4"] = datetime(2001, 1, 31), datetime(2001, 2, 28)  # typed dates
    calc["A3"] = "=SUM(Data!H3:H4)"  # dates only upstream: a workbook calculation
    stream = BytesIO()
    book.save(stream)
    formulas = load_workbook(BytesIO(stream.getvalue()))
    cached = load_workbook(BytesIO(stream.getvalue()), data_only=True)
    cached["Data"]["A1"].value = "SPX Index"
    return provenance.WorkbookTracer(formulas, cached)


def test_workbook_cells_are_traced_to_their_origin():
    tracer = traced_workbook()
    (bdh,) = tracer.classify("Data", "C3")
    assert (bdh["provider"], bdh["detail"]) == ("Bloomberg", "HOMECOMP Index PX_LAST")
    (bdp,) = tracer.classify("Data", "E2")
    assert bdp["detail"] == "SPX Index PX_LAST"
    assert tracer.classify("Data", "F2") == [provenance.source("workbook:manual")]
    assert tracer.classify("Data", "G2") == [provenance.source("workbook:calculated")]
    assert provenance.providers(tracer.classify("Data", "F2")) == [
        "PCM - Monthly Market & Risk Monitor (manual input)"
    ]
    assert provenance.providers(tracer.classify("Calc", "A1")) == ["Bloomberg"]
    assert set(provenance.providers(tracer.classify("Calc", "A2"))) == {
        "Bloomberg",
        "PCM - Monthly Market & Risk Monitor (manual input)",
    }
    assert provenance.providers(tracer.classify("Calc", "A3")) == [
        "PCM - Monthly Market & Risk Monitor (calculated)"
    ]


def save_observations(key, url):
    values = pd.Series(np.linspace(1, 2, 30), index=pd.date_range("2024-01-01", periods=30))
    store.save({**BY_ID[key], "url": url}, values)


def test_label_follows_the_stored_download_url():
    from dashboard.sections.common import current_source, load

    save_observations("DGS10", BY_ID["DGS10"]["url"])
    assert current_source("DGS10").startswith("FRED (DGS10")
    # The same series later downloaded from another site is relabelled automatically.
    save_observations("UNRATE", "https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000")
    assert provenance.providers(provenance.sources_of(load(["UNRATE"])["UNRATE"])) == ["BLS"]


def seed_workbook(section, series_id, values, sources):
    points = [
        {"date": d.date().isoformat(), "value": v, "cell": "Z1", "forward": False, "formula": None}
        for d, v in values.items()
    ]
    payload = {
        "sections": {
            section: {
                "notes": [],
                "tables": [],
                "charts": [
                    {
                        "id": "c",
                        "title": "c",
                        "series": [{"id": series_id, "points": points, "sources": sources}],
                    }
                ],
            }
        },
        "metric_count": 1,
        "latest_observation": None,
        "diagnostics": {},
        "issues": [],
    }
    with Session(store.engine) as session, session.begin():
        session.add(
            store.WorkbookImport(
                imported_at=datetime.now(UTC),
                path="synthetic.xlsx",
                sha256="0" * 64,
                status="success",
                payload=json.dumps(payload),
            )
        )


def test_declared_bloomberg_equivalent_replaces_fred(monkeypatch):
    from dashboard.sections.common import current_source, load

    save_observations("DGS10", BY_ID["DGS10"]["url"])
    dates = pd.date_range("2024-01-31", periods=6, freq="ME")
    bloomberg = [
        provenance.source(
            "Bloomberg", "USGG10YR Index PX_LAST", "PCM - Monthly Market & Risk Monitor"
        )
    ]
    seed_workbook("Rates", "rates_10y", pd.Series(4.0, index=dates), bloomberg)

    # Not declared equivalent: FRED stays, the workbook series is never substituted silently.
    assert provenance.providers(provenance.sources_of(load(["DGS10"])["DGS10"])) == ["FRED"]

    config = {
        **provenance.config(),
        "equivalents": {"DGS10": {"section": "Rates", "series": "rates_10y"}},
    }
    monkeypatch.setattr(provenance, "config", lambda: config)
    series = load(["DGS10"])["DGS10"]
    assert provenance.providers(provenance.sources_of(series)) == ["Bloomberg"]
    assert len(series) == 6
    assert current_source("DGS10").startswith("Bloomberg (USGG10YR Index")

    # A manual workbook series does not outrank a FRED download.
    seed_workbook("Rates", "rates_10y", pd.Series(4.0, index=dates), [])
    assert provenance.providers(provenance.sources_of(load(["DGS10"])["DGS10"])) == ["FRED"]


def test_chart_caption_lists_sources_and_derived_lines():
    from dashboard.styles.theme import chart_source_text

    provenance.reset_page()
    provenance.note_page([provenance.source("FRED", "VIXCLS")])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1], y=[1], meta={"sources": [provenance.source("FRED", "VIXCLS")]}))
    assert chart_source_text(fig) == "Source: FRED (VIXCLS)"
    fig.add_trace(go.Scatter(x=[1], y=[2]))  # e.g. a ratio computed on the page
    assert chart_source_text(fig).endswith(
        "other lines calculated from this page's inputs (FRED (VIXCLS))"
    )
    derived = go.Figure(go.Heatmap(z=[[1, 2]]))
    assert chart_source_text(derived) == "Source: calculated from this page's inputs: FRED (VIXCLS)"


def test_checklist_source_text_follows_the_data(monkeypatch):
    from dashboard.sections import extras

    monkeypatch.setattr(
        extras, "current_sources", lambda key: [provenance.source("Bloomberg", key)]
    )
    assert extras.live_source("FRED: VIXCLS, VXVCLS") == "Bloomberg (VIXCLS; VXVCLS)"
    assert extras.live_source("Workbook (saved manual flag)") == "Workbook (saved manual flag)"
    monkeypatch.setattr(extras, "current_sources", lambda key: [])
    assert extras.live_source("FRED: VIXCLS") == "FRED: VIXCLS"  # nothing loaded: rule text kept


@pytest.mark.parametrize("title", ["Market Data", "Recession"])
def test_pages_caption_each_chart_with_its_source(title):
    for key in ["SP500", "DGS2", "DGS10", "UNRATE", "T10Y3M", "SAHMREALTIME", "USREC"]:
        save_observations(key, BY_ID[key]["url"])
    script = f"""from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace = runpy.run_path({str(ROOT / "dashboard/app.py")!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""
    app = AppTest.from_string(script).run(timeout=60)
    assert not app.exception
    captions = [c.value for c in app.caption if c.value.startswith("Source:")]
    assert captions
    assert any("FRED" in c for c in captions)


def test_labels_are_named_when_shown_so_renames_apply_to_old_snapshots(monkeypatch):
    stored = [
        provenance.source("Bloomberg", "SPX Index PX_LAST", "workbook:via"),
        provenance.source("workbook:manual"),
    ]
    assert provenance.describe(stored) == (
        "Bloomberg (SPX Index PX_LAST) via PCM - Monthly Market & Risk Monitor · "
        "PCM - Monthly Market & Risk Monitor (manual input)"
    )
    # Snapshots imported before stable keys stored the old wording; it is shown with the new name.
    legacy = [
        provenance.source("Bloomberg", "SPX Index PX_LAST", "sponsor workbook"),
        provenance.source("Sponsor workbook (calculated)"),
    ]
    assert "ponsor" not in provenance.describe(legacy)
    # A later rename in config/providers.json applies immediately, without re-importing.
    config = {**provenance.config()}
    config["workbook"] = {**config["workbook"], "manual": "Workbook (typed in)"}
    monkeypatch.setattr(provenance, "config", lambda: config)
    assert provenance.providers(stored) == ["Bloomberg", "Workbook (typed in)"]
