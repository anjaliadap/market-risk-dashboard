"""Render complete workbook pages from synthetic, isolated database fixtures."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from dashboard import workbook_sections
from src.database import store
from src.providers.workbook_sections import AAII_IDS, STRATEGY_IDS
from src.registry import BY_ID

ROOT = Path(__file__).resolve().parents[1]


def render_page(title):
    # Both imported enqueue aliases remain patched for the entire render,
    # including the fragment body. No test launches real provider retrieval.
    script = f"""from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'), patch('dashboard.workbook_sections.enqueue'):
    namespace = runpy.run_path({str(ROOT / "dashboard/app.py")!r})
    namespace['render']({title!r})
"""
    return AppTest.from_string(script).run(timeout=30)


def metrics(app):
    return {metric.label: metric.value for metric in app.metric}


def status_table(app):
    return next(table.value for table in app.dataframe if "Status" in table.value.columns)


def btc_table(app):
    return next(table.value for table in app.dataframe if "Metric" in table.value.columns)


@pytest.fixture
def populated_sections(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "populated_sections.db"))
    monkeypatch.setattr(store, "engine", engine)
    monkeypatch.setattr(workbook_sections, "engine", engine)
    store.initialize()
    now = datetime.now(UTC)
    today = pd.Timestamp(now).tz_localize(None).normalize()

    last_quarter = today.to_period("Q") - 1
    quarters = pd.period_range(end=last_quarter, periods=8, freq="Q")
    months = pd.period_range(quarters[0].start_time, last_quarter.end_time, freq="M")
    margin = pd.Series(np.linspace(500_000, 800_000, len(months)), index=months.to_timestamp("M"))
    gdp = pd.Series(np.linspace(25_000, 28_000, len(quarters)), index=quarters.to_timestamp())
    capitalization = pd.Series(
        np.linspace(30_000_000, 40_000_000, len(quarters)), index=quarters.to_timestamp()
    )
    for key, values in [
        ("FINRA_MARGIN_DEBT", margin),
        ("GDP", gdp),
        ("BOGZ1LM883164115Q", capitalization),
    ]:
        store.save(BY_ID[key], values)

    survey_dates = pd.date_range(end=today - pd.Timedelta(days=1), periods=104, freq="W-THU")
    bulls = np.linspace(24, 50, len(survey_dates))
    bears = np.linspace(52, 26, len(survey_dates))
    sentiments = pd.DataFrame(
        {
            "AAII_BULLISH": bulls,
            "AAII_NEUTRAL": 100 - bulls - bears,
            "AAII_BEARISH": bears,
            "AAII_SP500_WEEKLY_CLOSE": 4000 + np.arange(len(survey_dates)) * 8,
        },
        index=survey_dates,
    )
    store.save_many([(BY_ID[key], sentiments[key]) for key in AAII_IDS])

    snapshot_date = today - pd.Timedelta(days=7)
    company_values = {
        "STRATEGY_BTC_HOLDINGS": 1000.0,
        "STRATEGY_DEBT_USD": 20_000_000.0,
        "STRATEGY_PREFERRED_USD": 5_000_000.0,
        "STRATEGY_BTC_COST_USD": 60_000.0,
    }
    company = {
        key: pd.Series([value], index=pd.DatetimeIndex([snapshot_date]))
        for key, value in company_values.items()
    }
    store.save_many([(BY_ID[key], company[key]) for key in STRATEGY_IDS])
    quote = pd.Series([100_000.0], index=pd.DatetimeIndex([today]))
    quote.attrs["published_at"] = now
    store.save(BY_ID["COINBASE_BTC_SPOT"], quote)
    yield {"now": now, "company": company, "quote": quote}
    engine.dispose()


@pytest.mark.parametrize(
    "title,expected_metrics,charts,tables",
    [
        (
            "Margin Debt",
            {
                "Customer margin debit balances": "$800.0 billion",
                "Margin debt / nominal GDP": "2.86%",
                "Margin debt / Fed public equity value (proxy)": "2.00%",
            },
            2,
            2,
        ),
        (
            "Bull vs Bear",
            {
                "Bullish − bearish": "+24.0 pp",
                "Historical percentile": "100",
                "Current decile": "10 / 10",
            },
            1,
            3,
        ),
        (
            "BTC",
            {
                "BTC / debt + preferred coverage": "4.00×",
                "BTC price for 1:1 coverage": "$25,000",
                "Change to 1:1 coverage price": "-75.0%",
            },
            0,
            2,
        ),
    ],
)
def test_populated_workbook_page_outputs(
    populated_sections, title, expected_metrics, charts, tables
):
    app = render_page(title)
    assert not app.exception
    assert app.title[0].value == title
    assert metrics(app) == expected_metrics
    assert len(app.get("plotly_chart")) == charts
    assert len(app.dataframe) == tables
    statuses = status_table(app)
    assert len(statuses) == len(workbook_sections.PAGE_IDS[title])
    assert not statuses.Status.str.contains("UNAVAILABLE|failed", case=False).any()
    if title == "Bull vs Bear":
        returns = next(table.value for table in app.dataframe if "Sentiment" in table.value.columns)
        assert len(returns) == 10
        assert returns.loc[1, "Sentiment"] == "Bearish"
        assert returns.loc[10, "Sentiment"] == "Bullish"
        assert returns["1M mean (%)"].notna().any()
        captions = " ".join(caption.value for caption in app.caption)
        assert "excluding dividends" in captions
        assert "Only completed horizons" in captions
    if title == "BTC":
        calculated = btc_table(app).set_index("Metric")
        assert len(calculated) == 10
        assert calculated.loc["BTC market value", "Value"] == pytest.approx(100)
        assert calculated.loc["Total debt + preferred", "Value"] == pytest.approx(25)
        assert calculated.loc["Loan to value", "Value"] == pytest.approx(25)
        assert calculated.loc["Unrealized gain / loss", "Value"] == pytest.approx(40)


def test_missing_margin_denominators_show_safe_warnings(populated_sections):
    with Session(store.engine) as session, session.begin():
        session.execute(
            delete(store.Observation).where(
                store.Observation.series_id.in_(["GDP", "BOGZ1LM883164115Q"])
            )
        )
    app = render_page("Margin Debt")
    assert not app.exception
    assert metrics(app) == {"Customer margin debit balances": "$800.0 billion"}
    assert len(app.get("plotly_chart")) == 0
    assert sum("valid denominator" in warning.value for warning in app.warning) == 2
    assert status_table(app).Status.str.contains("UNAVAILABLE").sum() == 2


def test_missing_company_input_suppresses_coverage_outputs(populated_sections):
    with Session(store.engine) as session, session.begin():
        session.execute(
            delete(store.Observation).where(store.Observation.series_id == "STRATEGY_PREFERRED_USD")
        )
    app = render_page("BTC")
    assert not app.exception
    assert not app.metric
    assert not any("Metric" in table.value.columns for table in app.dataframe)
    assert any("Coverage calculations await" in info.value for info in app.info)


def test_saved_stale_quote_and_failed_source_remain_visible_with_dates(populated_sections):
    quote = populated_sections["quote"].copy()
    quote.attrs["published_at"] = populated_sections["now"] - timedelta(days=2)
    store.save(BY_ID["COINBASE_BTC_SPOT"], quote)
    with Session(store.engine) as session, session.begin():
        session.add(
            store.Job(
                series_id="COINBASE_BTC_SPOT",
                started_at=datetime.now(UTC),
                status="failed",
                error="simulated source outage; previous quote retained",
            )
        )
    app = render_page("BTC")
    assert not app.exception
    assert metrics(app)["BTC / debt + preferred coverage"] == "4.00×"
    assert any("stale or their refresh failed" in warning.value for warning in app.warning)
    statuses = status_table(app)
    spot = statuses.loc[statuses.Source.str.contains("coinbase", case=False)].iloc[0]
    assert "STALE" in spot.Status
    assert "refresh failed" in spot.Status
    assert "simulated source outage" in spot.Error
    assert spot["Source time (UTC)"] != "Not supplied"


def test_incoherent_company_vintages_suppress_coverage(populated_sections):
    debt = populated_sections["company"]["STRATEGY_DEBT_USD"].copy()
    debt.iloc[0] = 21_000_000
    store.save(BY_ID["STRATEGY_DEBT_USD"], debt)
    app = render_page("BTC")
    assert not app.exception
    assert not app.metric
    assert any("one source snapshot" in warning.value for warning in app.warning)
    assert not any("Metric" in table.value.columns for table in app.dataframe)


def test_one_company_field_revision_preserves_group_coherence_and_coverage_table(
    populated_sections,
):
    before = render_page("BTC")
    assert not before.exception
    revised = {key: values.copy() for key, values in populated_sections["company"].items()}
    revised["STRATEGY_DEBT_USD"].iloc[0] = 25_000_000
    changed = store.save_many([(BY_ID[key], revised[key]) for key in STRATEGY_IDS])
    assert changed == dict.fromkeys(STRATEGY_IDS, 1)
    vintages = {store.history(key).retrieved_at.iloc[-1] for key in STRATEGY_IDS}
    assert len(vintages) == 1
    after = render_page("BTC")
    assert not after.exception
    assert metrics(after)["BTC / debt + preferred coverage"] == "3.33×"
    assert metrics(after)["BTC price for 1:1 coverage"] == "$30,000"
    assert metrics(after)["Change to 1:1 coverage price"] == "-70.0%"
    assert len(btc_table(after)) == 10
    assert not any("one source snapshot" in warning.value for warning in after.warning)


@pytest.mark.parametrize("title", list(workbook_sections.PAGE_IDS))
def test_imported_workbook_remains_selectable_on_public_sections(title):
    script = f"""from unittest.mock import patch
import runpy
import streamlit as st
with patch('streamlit.navigation'), patch('src.refresh.enqueue'), patch('dashboard.workbook_sections.enqueue'):
    namespace = runpy.run_path({str(ROOT / "dashboard/app.py")!r})
    def saved_workbook(name):
        st.info('Imported snapshot for ' + name)
        return True
    with patch.dict(namespace, render_section=saved_workbook):
        namespace['render']({title!r})
"""
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    assert app.radio[0].value == "Public data (automatic updates)"
    assert not any("Imported snapshot for" in info.value for info in app.info)
    app.radio[0].set_value("Imported workbook snapshot").run(timeout=30)
    assert not app.exception
    assert any("Imported snapshot for " + title == info.value for info in app.info)
    assert not app.metric
