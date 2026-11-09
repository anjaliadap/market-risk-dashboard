"""Consumer: income and spending, balance-sheet burden, credit growth, stress and sentiment."""

import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    Kpi,
    chart_or_note,
    clip,
    cross_check,
    derived_metric,
    kpi_row,
    line_figure,
    load,
    lookback_start,
    page_tabs,
    refresh_controls,
    render_workbook,
    snapshot_table,
    sources_table,
    yoy,
)
from src.analytics.sectors import real_growth

IDS = [
    "PSAVERT",
    "DSPIC96",
    "PCEC96",
    "RSAFS",
    "CES0500000003",
    "CPIAUCSL",
    "UNRATE",
    "TDSP",
    "MDSP",
    "CDSP",
    "TOTALSL",
    "REVOLSL",
    "NONREVSL",
    "DRCCLACBS",
    "CORCCACBS",
    "UMCSENT",
    "USREC",
]
KPIS = [
    Kpi("PSAVERT", "Saving rate", "{:.1f}%", "yoy_pp"),
    Kpi("TDSP", "Debt service", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("TOTALSL", "Consumer credit", "${:,.0f}bn", "yoy_pct"),
    Kpi("DRCCLACBS", "Card delinquency", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("UMCSENT", "UMich sentiment", "{:.1f}", "prior"),
    Kpi("UNRATE", "Unemployment", "{:.1f}%", "yoy_pp", inverse=True),
]
TABLE = [
    ("PSAVERT", "pp"),
    ("DSPIC96", "pct"),
    ("PCEC96", "pct"),
    ("RSAFS", "pct"),
    ("CES0500000003", "pct"),
    ("CPIAUCSL", "pct"),
    ("UNRATE", "pp"),
    ("TDSP", "pp"),
    ("MDSP", "pp"),
    ("CDSP", "pp"),
    ("TOTALSL", "pct"),
    ("REVOLSL", "pct"),
    ("NONREVSL", "pct"),
    ("DRCCLACBS", "pp"),
    ("CORCCACBS", "pp"),
    ("UMCSENT", "pp"),
]
CROSS_CHECKS = [
    ("consumer_0_0", "HH Debt Service Ratio", "TDSP"),
    ("consumer_1_0", "Consumer Credit Outstanding", "TOTALSL"),
    ("consumer_2_0", "US Personal Savings Rate", "PSAVERT"),
]
NOTES = [
    (
        "Saving rate is personal saving as a percent of disposable personal income (BEA). Debt service "
        "ratios are required payments as a percent of disposable income (Fed); the denominators match "
        "each other but the measures answer different questions."
    ),
    (
        "Real wage growth ≈ average hourly earnings Y/Y minus CPI-U Y/Y (both monthly, SA); an "
        "approximation, not a deflated wage index."
    ),
    (
        "Real income and spending are chained 2017 dollars, SAAR. Retail sales are nominal and include "
        "food services; they are not deflated here."
    ),
    (
        "Consumer credit (G.19) excludes mortgages; revolving is mostly credit cards. Card delinquency "
        "and charge-offs are commercial-bank measures shared with the Banks page."
    ),
    (
        "UMich sentiment is redistributed on FRED with a delay under license; preliminary readings are "
        "not ingested."
    ),
    "Shaded areas are NBER recessions (USREC). Observation dates are not release dates.",
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        kpi_row(data, KPIS)
        start = lookback_start("consumer")
        _income_and_spending(ctx, data, start)
        _balance_sheet(ctx, data, start)
        _stress_and_sentiment(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "consumer_indicators.csv")
        with st.expander("Workbook vs independent source cross-check"):
            cross_check(ctx, data, ctx.title, CROSS_CHECKS, "consumer_xc")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _income_and_spending(ctx, data, start):
    st.subheader("Income, spending & real wages")
    wage = yoy(data, "CES0500000003")
    inflation = yoy(data, "CPIAUCSL")
    real_wage = (
        real_growth(wage, inflation) if not (wage.empty or inflation.empty) else wage.iloc[0:0]
    )
    a, b, c = st.columns(3)
    for column, label, series in (
        (a, "Real disposable income Y/Y", yoy(data, "DSPIC96")),
        (b, "Real spending Y/Y", yoy(data, "PCEC96")),
        (c, "Real wage growth", real_wage),
    ):
        derived_metric(column, label, series, "{:+.1f}%", "percent Y/Y")
    left, right = st.columns(2)
    with left:
        series = {
            "Real disposable income": clip(yoy(data, "DSPIC96"), start),
            "Real PCE": clip(yoy(data, "PCEC96"), start),
            "Retail sales (nominal)": clip(yoy(data, "RSAFS"), start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Income vs spending growth (% Y/Y)",
                series,
                left_title="Percent",
                zero=True,
            ),
            [series],
            "consumer_income",
            "Income/spending series not ingested.",
            data,
            start,
        )
    with right:
        series = {
            "Avg hourly earnings": clip(wage, start),
            "CPI-U": clip(inflation, start),
            "Real wage (approx.)": clip(real_wage, start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Wages vs inflation (% Y/Y)", series, left_title="Percent", zero=True
            ),
            [series],
            "consumer_wages",
            "Requires average hourly earnings and CPI.",
            data,
            start,
        )


def _balance_sheet(ctx, data, start):
    st.subheader("Savings, debt burden & credit growth")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        burden = {
            "Total debt service": clip(data.get("TDSP", empty), start),
            "Mortgage": clip(data.get("MDSP", empty), start),
            "Consumer": clip(data.get("CDSP", empty), start),
        }
        saving = {"Saving rate": clip(data.get("PSAVERT", empty), start)}
        chart_or_note(
            ctx,
            line_figure(
                "Debt service ratios vs saving rate (% of disposable income)",
                burden,
                saving,
                "Debt service, %",
                "Saving rate, %",
            ),
            [burden, saving],
            "consumer_burden",
            "Debt service / saving series not ingested.",
            data,
            start,
        )
    with right:
        growth = {
            "Revolving": clip(yoy(data, "REVOLSL"), start),
            "Nonrevolving": clip(yoy(data, "NONREVSL"), start),
            "Total": clip(yoy(data, "TOTALSL"), start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Consumer credit growth (% Y/Y)", growth, left_title="Percent", zero=True
            ),
            [growth],
            "consumer_credit",
            "G.19 consumer credit not ingested.",
            data,
            start,
        )


def _stress_and_sentiment(ctx, data, start):
    st.subheader("Credit stress & sentiment")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        series = {
            "Card delinquency": clip(data.get("DRCCLACBS", empty), start),
            "Card net charge-offs": clip(data.get("CORCCACBS", empty), start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "Credit card delinquency and charge-offs (%, SA)", series, left_title="Percent"
            ),
            [series],
            "consumer_cards",
            "Card credit-quality series not ingested.",
            data,
            start,
        )
    with right:
        sentiment = {"UMich sentiment": clip(data.get("UMCSENT", empty), start)}
        unemployment = {"Unemployment rate": clip(data.get("UNRATE", empty), start)}
        chart_or_note(
            ctx,
            line_figure("Sentiment vs labor market", sentiment, unemployment, "Index", "Percent"),
            [sentiment, unemployment],
            "consumer_sentiment",
            "Sentiment/unemployment not ingested.",
            data,
            start,
        )
