"""AI Supply: no sponsor workbook tab exists. Public bottleneck proxies (backlogs, equipment
prices, utilization) plus append-only analyst logs for GPU rental prices, data-center capacity,
vacancy and lead times, which have no free machine-readable feed."""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    Kpi,
    chart_or_note,
    clip,
    kpi_row,
    line_figure,
    load,
    lookback_start,
    refresh_controls,
    snapshot_table,
    sources_table,
    yoy,
)
from dashboard.sections.extras import add_reference, analyst_log, checklist
from src.analytics.signals import Check, last, ratio

IDS = [
    "A35SUO",
    "A35SVS",
    "A34SUO",
    "A34SVS",
    "PCU335311335311",
    "PCU333611333611",
    "CAPUTLG3344S",
    "IPG2211S",
    "USREC",
]
KPIS = [
    Kpi("PCU335311335311", "Transformer PPI", "{:.1f}", "yoy_pct", inverse=True),
    Kpi("PCU333611333611", "Turbine & generator PPI", "{:.1f}", "yoy_pct", inverse=True),
    Kpi("CAPUTLG3344S", "Semis capacity use", "{:.1f}%", "yoy_pp", inverse=True),
    Kpi("IPG2211S", "Electric power output", "{:.1f}", "yoy_pct"),
]
TABLE = [
    ("A35SUO", "pct"),
    ("A35SVS", "pct"),
    ("A34SUO", "pct"),
    ("A34SVS", "pct"),
    ("PCU335311335311", "pct"),
    ("PCU333611333611", "pct"),
    ("CAPUTLG3344S", "pp"),
    ("IPG2211S", "pct"),
]
BASELINE = ("2015-01-01", "2019-12-31")
SOURCES = {
    "gpu_pricing": (
        "Record public list prices from provider pricing pages and marketplaces, one chip and "
        "pricing type per row. Be explicit: on-demand, spot/interruptible, or contracted/reserved "
        "(note the term). Normalize multi-GPU instance prices to USD per GPU-hour."
    ),
    "dc_capacity": (
        "Broker market reports (e.g., CBRE, JLL, Cushman & Wakefield data-center updates) report "
        "operational and under-construction MW by market. Record the report date as the "
        "observation date."
    ),
    "dc_vacancy": (
        "Use the same broker reports for vacancy rate (%) and available supply (MW). Keep the "
        "market definition consistent across reports."
    ),
    "lead_times": (
        "Lead times in weeks from industry surveys, utility filings or manufacturer commentary "
        "(earnings calls). Cite the specific document."
    ),
}
NOTES = [
    (
        "The sponsor has no Bloomberg tab for Supply. This page is a proposed structure: public "
        "proxies that are refreshed automatically, plus analyst logs for items the sponsor listed "
        "(capacity, vacancy, available supply, lead times, GPU rental prices)."
    ),
    (
        "Backlog (months) = unfilled orders ÷ monthly shipments (Census M3, SA, nominal). Rising "
        "backlog months indicate demand outrunning delivery capacity, a proxy for lead times."
    ),
    (
        "Pre-2020 baseline = 2015–2019. Bottleneck signals compare the latest reading with that "
        "baseline; thresholds are stated in each rule."
    ),
    (
        "Transformer and turbine PPIs are industry producer price indexes (not seasonally "
        "adjusted). Price acceleration in grid equipment is a symptom of supply constraints."
    ),
    (
        "Analyst observations are append-only, require a source link, and are never "
        "interpolated, scraped or estimated by the application."
    ),
]


def render(ctx, render_section):
    data = load(IDS)
    labels = [
        "Bottleneck indicators",
        "Analyst-sourced data",
        "Indicators",
        "Methodology & sources",
    ]
    proxies, analyst, indicators, method = st.tabs(labels)
    with proxies:
        st.info(
            "No sponsor workbook source exists for Supply. Indicators below are public proxies; "
            "direct capacity, vacancy and GPU pricing data are recorded in Analyst-sourced data."
        )
        refresh_controls(ctx, IDS)
        _signal_board(ctx, data)
        kpi_row(data, KPIS)
        start = lookback_start("supply", "10Y")
        _backlogs(ctx, data, start)
        _equipment(ctx, data, start)
    with analyst:
        for dataset, guidance in SOURCES.items():
            with st.container(border=True):
                analyst_log(ctx, dataset, "supply_" + dataset)
                st.caption(guidance)
    with indicators:
        snapshot_table(ctx, data, TABLE, "supply_indicators.csv")
    with method:
        sources_table(ctx, IDS, NOTES)


def backlog(data, unfilled, shipments):
    return ratio(data.get(unfilled), data.get(shipments))


def _baseline(series):
    s = series.dropna().loc[BASELINE[0] : BASELINE[1]]
    return (float(s.mean()), float(s.max())) if len(s) else (np.nan, np.nan)


def _signal_board(ctx, data):
    st.subheader("Bottleneck signal board")
    st.caption("RED = a supply constraint is visible in the public proxy.")
    checks = []
    for label, unfilled, shipments, source in (
        ("Electrical equipment backlog", "A35SUO", "A35SVS", "FRED: A35SUO ÷ A35SVS"),
        ("Computer & electronics backlog", "A34SUO", "A34SVS", "FRED: A34SUO ÷ A34SVS"),
    ):
        months = backlog(data, unfilled, shipments)
        now, as_of = last(months)
        mean, peak = _baseline(months)
        c = Check(
            label,
            "Above pre-2020 range",
            "Unfilled orders ÷ monthly shipments above its 2015–2019 maximum",
            source=source,
        )
        if not (np.isnan(now) or np.isnan(peak)):
            c.red, c.as_of = now > peak, as_of
            c.status = "Above pre-2020 range" if c.red else "Within pre-2020 range"
            c.reading = f"{now:.2f} months (2015–19 avg {mean:.2f}, max {peak:.2f})"
        checks.append(c)
    for label, key in (
        ("Transformer prices", "PCU335311335311"),
        ("Turbine & generator prices", "PCU333611333611"),
    ):
        growth = yoy(data, key).dropna()
        now, as_of = last(growth)
        c = Check(
            label, "> 10% Y/Y", "Producer price index up more than 10% Y/Y", source="FRED: " + key
        )
        if not np.isnan(now):
            c.red, c.as_of = now > 10, as_of
            c.status = "Rapid inflation" if c.red else "Contained"
            c.reading = f"{now:+.1f}% Y/Y"
        checks.append(c)
    now, as_of = last(data.get("CAPUTLG3344S"))
    c = Check(
        "Semiconductor capacity utilization",
        "> 80%",
        "US semiconductor & electronic component utilization above 80%",
        source="FRED: CAPUTLG3344S",
    )
    if not np.isnan(now):
        c.red, c.as_of = now > 80, as_of
        c.status = "Tight" if c.red else "Spare capacity"
        c.reading = f"{now:.1f}%"
    checks.append(c)
    checklist(ctx, checks, "supply_signal_board", "bottleneck signals")


def _backlogs(ctx, data, start):
    st.subheader("Order backlogs (lead-time proxy)")
    series = {
        "Electrical equipment": clip(backlog(data, "A35SUO", "A35SVS"), start),
        "Computers & electronics": clip(backlog(data, "A34SUO", "A34SVS"), start),
    }
    fig = line_figure(
        "DERIVED · Months of backlog (unfilled orders ÷ monthly shipments)",
        series,
        left_title="Months",
    )
    mean, _ = _baseline(backlog(data, "A35SUO", "A35SVS"))
    if not np.isnan(mean):
        add_reference(fig, mean, "electrical 2015–19 avg", dash="dot")
    chart_or_note(
        ctx, fig, [series], "supply_backlog", "Census M3 series not ingested.", data, start
    )


def _equipment(ctx, data, start):
    st.subheader("Power equipment prices & grid output")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        series = {
            "Transformers": clip(_rebased(data.get("PCU335311335311", empty)), start),
            "Turbines & generator sets": clip(_rebased(data.get("PCU333611333611", empty)), start),
        }
        fig = line_figure(
            "DERIVED · Grid equipment producer prices (Dec 2019 = 100)",
            series,
            left_title="Index",
        )
        add_reference(fig, 100, "Dec 2019", dash="dot")
        chart_or_note(ctx, fig, [series], "supply_ppi", "PPI series not ingested.", data, start)
    with right:
        output = {"Electric power output Y/Y": clip(yoy(data, "IPG2211S"), start)}
        utilization = {"Semis capacity utilization": clip(data.get("CAPUTLG3344S", empty), start)}
        fig = line_figure(
            "Electric power output vs semiconductor utilization",
            output,
            utilization,
            "Percent Y/Y",
            "Percent of capacity",
            zero=True,
        )
        chart_or_note(
            ctx, fig, [output, utilization], "supply_power", "Inputs not ingested.", data, start
        )


def _rebased(series):
    s = series.dropna()
    base = s.loc[:"2019-12-31"]
    if s.empty or base.empty or base.iloc[-1] <= 0:
        return pd.Series(dtype=float)
    return s / base.iloc[-1] * 100
