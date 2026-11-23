"""Synthetic-only checks of source ownership, labels and unavailable-value behavior."""

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.process_sections import PAGE_TITLES, build_gold_figure, build_trend_figure


@pytest.fixture
def snapshot():
    return {
        "sha256": "synthetic-checksum",
        "latest_observation": "2025-09-30",
        "issues": [],
        "sections": {
            "Gold to Oil": {
                "history": [
                    {"date": "2025-08-31", "gold": 2000, "oil": 80, "ratio": 25, "average": 30},
                    {"date": "2025-09-30", "gold": 2100, "oil": 70, "ratio": 30, "average": 30},
                ],
                "current": {
                    "date": "2025-09-30",
                    "gold": 2100,
                    "oil": 70,
                    "ratio": 30,
                    "average": 30,
                },
                "implied": [
                    {"asset": "Gold", "current": 2100, "implied": 2100, "change": 0},
                    {"asset": "Brent futures", "current": 70, "implied": 70, "change": 0},
                ],
            },
            "Intra-Sector Spread": {
                "as_of": "2025-09-30",
                "dates": ["2025-08-31", "2025-09-30"],
                "history": [],
                "current": [
                    {
                        "sector": "Synthetic sector",
                        "percentile": 72,
                        "average": 50,
                        "change_1m": 4,
                        "change_3m": -3,
                        "change_6m": None,
                        "change_12m": None,
                    }
                ],
            },
            "Trend Following": {
                "history": [
                    {"date": "2025-08-31", "quintile": 2},
                    {"date": "2025-09-30", "quintile": 4},
                ],
                "current": {
                    "date": "2025-09-30",
                    "quintile": 4,
                    "change_1m": 2,
                    "change_3m": -1,
                    "change_6m": None,
                    "change_12m": None,
                },
            },
            "NDR": {
                "as_of": None,
                "groups": [
                    {
                        "name": "Equities",
                        "rows": [
                            {
                                "model": "Synthetic model",
                                "reading": "Neutral",
                                "annualized_return": 0.05,
                                "start_year": 2000,
                            },
                            {
                                "model": "Next year's median gain",
                                "reading": None,
                                "annualized_return": 0.03,
                                "return_kind": "next_year_median",
                                "start_year": 2000,
                            },
                        ],
                    }
                ],
                "warnings": [
                    {
                        "model": "Synthetic watch",
                        "previous": 0.4,
                        "current": 0.5,
                        "threshold": 0.5,
                        "triggered": False,
                    }
                ],
            },
        },
    }


def render_page(title, snapshot=None, *, failed=False, configured=True, source_error=None):
    saved = (
        {"id": 1, "status": "success", "time": "2025-10-01T12:00:00", "snapshot": snapshot}
        if snapshot
        else None
    )
    newest = (
        {"id": 2, "status": "failed", "error": "Synthetic incomplete save"} if failed else saved
    )
    script = f"""from unittest.mock import patch
import streamlit as st
from dashboard.process_sections import render_process_section
saved = {saved!r}
newest = {newest!r}
def latest(success_only=False, profile=None):
    assert profile == 'process'
    return saved if success_only else newest
def poll(force=False):
    st.session_state['process_poll_force'] = force
    return 'Synthetic workbook ready'
with patch('dashboard.process_sections.latest_import', side_effect=latest), \\
     patch('dashboard.process_sections.poll_workbook', side_effect=poll), \\
     patch('dashboard.process_sections.configured_workbook_path', return_value={"/synthetic/latest.xlsx" if configured else ""!r}), \\
     patch('dashboard.process_sections.workbook_file_status', return_value={{'error': {source_error!r}}}), \\
     patch('httpx.Client.get', side_effect=AssertionError('No public data allowed')):
    st.title({title!r})
    st.write('Handled:', render_process_section({title!r}))
"""
    return AppTest.from_string(script).run(timeout=30)


@pytest.mark.parametrize("title", PAGE_TITLES)
def test_missing_process_import_owns_page_and_explains_configuration(title):
    app = render_page(title, configured=False)
    assert not app.exception
    assert any("No validated workbook snapshot" in item.value for item in app.info)
    assert any("PROCESS_WORKBOOK_PATH" in item.value for item in app.warning)
    assert not app.metric
    assert not app.get("plotly_chart")
    assert app.button[0].label == "Reimport source workbook"
    assert app.button[0].disabled


def test_configured_source_can_be_reimported_before_first_snapshot():
    app = render_page("NDR", configured=True)
    assert not app.exception
    assert not app.button[0].disabled
    assert not app.session_state["process_poll_force"]
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert app.session_state["process_poll_force"]


@pytest.mark.parametrize("title", PAGE_TITLES)
def test_saved_process_pages_render_without_network(snapshot, title):
    app = render_page(title, snapshot)
    assert not app.exception
    assert len(app.get("plotly_chart")) == (0 if title == "NDR" else 1)
    captions = " ".join(item.value for item in app.caption)
    assert "saved Excel workbook" in captions
    assert "Bloomberg refresh time unknown" in captions
    assert not app.warning


def test_gold_uses_futures_axis_and_provider_supplied_implied_values(snapshot):
    section = snapshot["sections"]["Gold to Oil"]
    figure = build_gold_figure(section)
    assert list(figure.data[0].y) == [25, 30]
    assert list(figure.data[2].y) == [80, 70]
    assert figure.data[2].yaxis == "y2"
    assert "barrel" in figure.layout.yaxis2.title.text
    app = render_page("Gold to Oil", snapshot)
    assert not app.exception
    assert {item.label: item.value for item in app.metric}["Brent futures (CO1)"] == "$70.00"
    assert [table.value.iloc[0, 1] for table in app.dataframe] == ["$2,100.00", "$70.00"]
    assert "front-month futures" in " ".join(item.value for item in app.caption)


def test_trend_keeps_quintiles_discrete_and_missing_changes_unavailable(snapshot):
    figure = build_trend_figure(snapshot["sections"]["Trend Following"])
    assert figure.data[0].line.shape == "hv"
    assert not figure.data[0].connectgaps
    app = render_page("Trend Following", snapshot)
    assert not app.exception
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Current quintile"] == "4 / 5"
    assert metrics["1M change"] == "+2"
    assert metrics["6M change"] == "Unavailable"


def test_ndr_distinguishes_median_return_and_does_not_invent_missing_reading(snapshot):
    app = render_page("NDR", snapshot)
    assert not app.exception
    table = app.dataframe[0].value.set_index("Model")
    assert table.loc["Next year's median gain", "Return basis"] == "Next-year median"
    assert table.loc["Next year's median gain", "Reading"] == "Unavailable"
    assert app.dataframe[1].value.loc[0, "Status"] == "At or below threshold"
    assert "undated saved snapshot" in " ".join(item.value for item in app.caption)


def test_failed_new_save_retains_previous_page_and_only_relevant_issues(snapshot):
    snapshot = deepcopy(snapshot)
    snapshot["issues"] = [
        {"sheet": "Gold to Oil", "cell": "Q1", "reason": "Synthetic display inconsistency"},
        {"sheet": "NDR", "cell": "C1", "reason": "Synthetic missing input"},
    ]
    app = render_page("Gold to Oil", snapshot, failed=True, source_error="Source disconnected")
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    warnings = " ".join(item.value for item in app.warning)
    assert "latest workbook import failed" in warnings
    assert "source workbook is unavailable" in warnings
    assert (
        "Source inconsistencies are shown below; calculated panels use the workbook inputs"
        in warnings
    )
    checks = next(table.value for table in app.dataframe if "reason" in table.value)
    assert checks.sheet.tolist() == ["Gold to Oil"]
    assert any("Synthetic incomplete save" in item.value for item in app.markdown)


def test_ndr_record_highs_calculator_preserves_labels_formats_and_scenario_dates(snapshot):
    snapshot["sections"]["NDR"]["calculator"] = {
        "rows": [
            {"label": "S&P 500 YE25", "value": 4000.5, "format": '"$"#,##0'},
            {"label": "% Gain", "value": 0.125, "format": "0.0%"},
            {"label": "Implied Upside to YE27", "value": 0.0575, "format": "0.00%"},
            {"label": "   Annualized", "value": None, "format": "0%"},
            {"label": "Scenario date", "value": "2025-09-30", "format": "mm-dd-yy"},
        ],
        "reference_date": "2025-09-30",
        "target_date": "2027-12-31",
        "notes": [
            "Scenario uses supplied assumptions; not model forecasts.",
            "Reference date is not the update date for manual model readings.",
        ],
    }
    app = render_page("NDR", snapshot)
    assert not app.exception
    assert any(item.label == "Record-highs calculation" for item in app.expander)
    table = app.dataframe[2].value
    assert table.Measure.tolist() == [
        "S&P 500 YE25",
        "% Gain",
        "Implied Upside to YE27",
        "   Annualized",
        "Scenario date",
    ]
    assert table.Value.tolist() == ["$4,001", "12.5%", "5.75%", "Unavailable", "2025-09-30"]
    captions = " ".join(item.value for item in app.caption)
    assert "reference date: 2025-09-30 · target date: 2027-12-31" in captions
    assert "not model forecasts" in captions
    assert "not the update date" in captions
