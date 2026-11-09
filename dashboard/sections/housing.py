"""Housing: rates and affordability, construction pipeline, sales/inventory, prices."""

import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    Kpi,
    chart_or_note,
    clip,
    cross_check,
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
from src.analytics.sectors import (
    align_asof,
    mortgage_payment,
    payment_series,
    payment_to_income,
)

IDS = [
    "MORTGAGE30US",
    "MORTGAGE15US",
    "HOUST",
    "HOUST1F",
    "PERMIT",
    "PERMIT1",
    "HSN1F",
    "MSACSR",
    "MSPUS",
    "CSUSHPINSA",
    "MEHOINUSA646N",
    "RHORUSQ156N",
    "DGS10",
    "USREC",
]
KPIS = [
    Kpi("MORTGAGE30US", "30Y mortgage", "{:.2f}%", "yoy_bp", inverse=True),
    Kpi("HOUST", "Housing starts", "{:,.0f}k", "yoy_pct"),
    Kpi("PERMIT1", "SF permits", "{:,.0f}k", "yoy_pct"),
    Kpi("HSN1F", "New home sales", "{:,.0f}k", "yoy_pct"),
    Kpi("MSACSR", "Months' supply", "{:.1f}", "yoy_abs", inverse=True),
    Kpi("CSUSHPINSA", "Case-Shiller", "{:,.1f}", "yoy_pct"),
]
TABLE = [
    ("MORTGAGE30US", "pp"),
    ("MORTGAGE15US", "pp"),
    ("HOUST", "pct"),
    ("HOUST1F", "pct"),
    ("PERMIT", "pct"),
    ("PERMIT1", "pct"),
    ("HSN1F", "pct"),
    ("MSACSR", "pp"),
    ("MSPUS", "pct"),
    ("CSUSHPINSA", "pct"),
    ("RHORUSQ156N", "pp"),
]
CROSS_CHECKS = [
    ("housing_0_1", "30Yr Mortgage (ILM3NAVG)", "MORTGAGE30US"),
    ("housing_3_0", "Single-Family Starts (NHSPS1)", "HOUST1F"),
    ("housing_3_1", "Single-Family Permits (NHSPA1)", "PERMIT1"),
]
NOTES = [
    (
        "Workbook affordability (HOMECOMP) is NAR's composite index; the payment-to-income measure "
        "here is an independent construction and is not a substitute for it."
    ),
    (
        "Payment = level 30-year P&I on the Census median sales price (MSPUS, quarterly) with the "
        "stated down payment, at the latest PMMS rate within 10 days. Excludes taxes, insurance and PMI."
    ),
    (
        "Income is Census nominal median household income (annual, published with a ~9-month lag); "
        "each quarter uses the latest annual value up to 24 months old, so recent ratios embed stale income."
    ),
    (
        "MSPUS covers new houses sold, not existing homes; existing-home sales, inventory and price "
        "remain workbook-only (NAR data is not redistributed on FRED in full history)."
    ),
    "Starts, permits and sales are seasonally adjusted annual rates in thousands of units.",
    (
        "Mortgage spread = PMMS 30-year (weekly, Thursday) minus the latest 10-year Treasury "
        "constant-maturity yield within 7 days, in basis points."
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
        start = lookback_start("housing")
        _rates_and_affordability(ctx, data, start)
        _pipeline(ctx, data, start)
        _sales_and_prices(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "housing_indicators.csv")
        with st.expander("Workbook vs independent source cross-check"):
            cross_check(ctx, data, ctx.title, CROSS_CHECKS, "housing_xc")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _rates_and_affordability(ctx, data, start):
    st.subheader("Rates & affordability")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        rates = {
            "30-year": clip(data.get("MORTGAGE30US", empty), start),
            "15-year": clip(data.get("MORTGAGE15US", empty), start),
        }
        spread = empty
        if {"MORTGAGE30US", "DGS10"} <= data.keys():
            pairs = align_asof(data["MORTGAGE30US"], data["DGS10"], 7)
            spread = (pairs["left"] - pairs["right"]) * 100
        chart_or_note(
            ctx,
            line_figure(
                "Freddie Mac PMMS mortgage rates",
                rates,
                {"30Y − 10Y Treasury (bp)": clip(spread, start)} if not spread.empty else None,
                "Percent",
                "Basis points",
            ),
            [rates],
            "housing_rates",
            "Mortgage rate history not ingested.",
            data,
            start,
        )
    with right:
        down = st.session_state.get("housing_down", 20) / 100
        payment = (
            payment_series(data["MSPUS"], data["MORTGAGE30US"], down)
            if {"MSPUS", "MORTGAGE30US"} <= data.keys()
            else empty
        )
        burden = (
            payment_to_income(payment, data["MEHOINUSA646N"])
            if "MEHOINUSA646N" in data and not payment.empty
            else empty
        )
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Monthly P&I on median new-home price",
                {"Monthly payment (USD)": clip(payment, start)},
                {"Payment / median income (%)": clip(burden, start)} if not burden.empty else None,
                "USD per month",
                "Percent of income",
            ),
            [{"p": payment}],
            "housing_payment",
            "Requires MSPUS and MORTGAGE30US.",
            data,
            start,
        )
    with st.expander("Mortgage payment calculator and rate sensitivity", expanded=False):
        a, b, c, d = st.columns(4)
        latest_price = data["MSPUS"].iloc[-1] if "MSPUS" in data else 400_000.0
        latest_rate = (
            min(max(data["MORTGAGE30US"].iloc[-1], 0.0), 25.0) if "MORTGAGE30US" in data else 6.5
        )
        price = a.number_input(
            "Home price (USD)", min_value=0.0, value=float(latest_price), step=5_000.0
        )
        down_pct = b.slider("Down payment (%)", 0, 50, 20, key="housing_down")
        rate = c.number_input(
            "Rate (%)", min_value=0.0, max_value=25.0, value=float(latest_rate), step=0.125
        )
        term = d.selectbox("Term (years)", [30, 20, 15], index=0)
        principal = price * (1 - down_pct / 100)
        base = mortgage_payment(principal, rate, term)
        st.metric("Monthly principal & interest", f"${base:,.0f}")
        shocks = [-200, -100, -50, 0, 50, 100, 200]
        table = pd.DataFrame(
            {
                "Rate shock (bp)": shocks,
                "Rate (%)": [max(rate + s / 100, 0) for s in shocks],
                "Monthly P&I (USD)": [
                    mortgage_payment(principal, max(rate + s / 100, 0), term) for s in shocks
                ],
            }
        )
        table["Change vs base (USD)"] = table["Monthly P&I (USD)"] - base
        ctx.table_view(table, hide_index=True)
        st.caption(
            "Defaults: latest stored MSPUS and PMMS 30-year rate when available; otherwise "
            "placeholder ASSUMPTIONS ($400,000 at 6.50%). P&I only."
        )


def _pipeline(ctx, data, start):
    st.subheader("Construction pipeline")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        levels = {
            "Total starts": clip(data.get("HOUST", empty), start),
            "Single-family starts": clip(data.get("HOUST1F", empty), start),
            "Single-family permits": clip(data.get("PERMIT1", empty), start),
        }
        chart_or_note(
            ctx,
            line_figure("Starts and permits (SAAR, thousands)", levels, left_title="Thousands"),
            [levels],
            "housing_pipeline",
            "Starts/permits not ingested.",
            data,
            start,
        )
    with right:
        growth = {
            "Single-family starts Y/Y": clip(yoy(data, "HOUST1F"), start),
            "Single-family permits Y/Y": clip(yoy(data, "PERMIT1"), start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Single-family Y/Y growth (%)", growth, left_title="Percent", zero=True
            ),
            [growth],
            "housing_pipeline_yoy",
            "Requires 12 months of starts/permits.",
            data,
            start,
        )
        st.caption(
            "Permits typically lead starts; sustained permit growth below starts signals a slowing pipeline."
        )


def _sales_and_prices(ctx, data, start):
    st.subheader("New-home sales, supply & prices")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        sales = {"New home sales (SAAR, k)": clip(data.get("HSN1F", empty), start)}
        supply = {"Months' supply": clip(data.get("MSACSR", empty), start)}
        chart_or_note(
            ctx,
            line_figure("New-home sales vs months' supply", sales, supply, "Thousands", "Months"),
            [sales, supply],
            "housing_sales",
            "New-home sales/supply not ingested.",
            data,
            start,
        )
    with right:
        prices = {
            "Case-Shiller national Y/Y": clip(yoy(data, "CSUSHPINSA"), start),
            "Median new-home price Y/Y": clip(yoy(data, "MSPUS"), start),
        }
        chart_or_note(
            ctx,
            line_figure("DERIVED · Home price growth (%)", prices, left_title="Percent", zero=True),
            [prices],
            "housing_prices",
            "Requires 12 months of price history.",
            data,
            start,
        )
        st.caption(
            "Case-Shiller is a repeat-sales index (NSA, ~2-month lag); MSPUS is a median of new homes "
            "sold and is affected by mix."
        )
