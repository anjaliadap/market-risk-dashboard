"""AI Supply: the PCM - Monthly Market & Risk Monitor's Supply tab (GPU rental prices, data-center
inventory and vacancy, North American capacity additions, backlog and years to build) leads.
Public bottleneck proxies (order backlogs, equipment prices, utilization) and append-only analyst
logs remain as independent cross-checks."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.sections.common import (
    Kpi,
    chart_or_note,
    clip,
    kpi_row,
    line_figure,
    load,
    lookback_start,
    refresh_controls,
    render_workbook,
    snapshot_table,
    sources_table,
    workbook_section,
    workbook_series,
    yoy,
)
from dashboard.sections.extras import add_reference, analyst_log, checklist, workbook_table
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
        "The PCM - Monthly Market & Risk Monitor's Supply tab is the primary source: H100 and "
        "B200 GPU rental price indexes (Bloomberg SDH100RT / SDB200RT, USD per GPU-hour; the "
        "last point is the current BDP price dated the day the workbook was saved), data-center "
        "inventory (MW) and vacancy, North American capacity additions (GW; 'E' periods are "
        "estimates) and backlog / years to build. The hardcoded blocks do not state their "
        "source in the workbook."
    ),
    (
        "B200 premium = B200 ÷ H100 rental price on the same month-end. Inventory growth "
        "compares the two latest saved periods as labelled in the workbook (half-years and "
        "years are mixed, so it is not annualized)."
    ),
    (
        "Public proxies (Census M3 backlogs, grid-equipment PPIs, utilization) are independent "
        "FRED cross-checks, refreshed automatically. Analyst logs cover items the workbook does "
        "not (other chips, contract pricing, lead times)."
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


WORKBOOK = "PCM - Monthly Market & Risk Monitor"


def render(ctx, render_section):
    data = load(IDS)
    order = [
        WORKBOOK,
        "Bottleneck indicators",
        "Analyst-sourced data",
        "Indicators",
        "Methodology & sources",
    ]
    # Workbook tab leads when a validated snapshot exists; otherwise the public proxies lead.
    labels = order if workbook_section(ctx.title) is not None else [order[1], order[0], *order[2:]]
    tabs = dict(zip(labels, st.tabs(labels), strict=True))
    workbook, proxies, analyst, indicators, method = (tabs[label] for label in order)
    with workbook:
        render_workbook(ctx.title, render_section)
        if workbook_section(ctx.title) is not None:
            _workbook_analytics(ctx)
    with proxies:
        st.caption(
            "Independent public proxies (FRED) for supply bottlenecks; the PCM workbook's Supply "
            "tab is the primary source for GPU pricing, data-center capacity and backlog."
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


# --- PCM workbook Supply tab ---------------------------------------------------------------------


def _workbook_analytics(ctx):
    st.subheader("Supply snapshot")
    h100 = workbook_series(ctx.title, "supply_0_0")
    b200 = workbook_series(ctx.title, "supply_0_1")
    inventory = workbook_table(ctx.title, "dc_inventory")
    additions = workbook_table(ctx.title, "capacity_additions")
    backlog = workbook_table(ctx.title, "backlog_build")
    a, b, c, d = st.columns(4)
    _price_tile(a, "H100 rental price", h100)
    _price_tile(b, "B200 rental price", b200)
    premium = ratio(b200, h100, 5)
    if len(premium.dropna()):
        b200_premium = premium.dropna()
        c.metric("B200 premium to H100", f"{b200_premium.iloc[-1]:.2f}×")
        c.caption(f"DERIVED · {b200_premium.index[-1].date()}")
    else:
        c.metric("B200 premium to H100", "—")
        c.caption("DERIVED · inputs unavailable")
    if len(inventory) >= 2:
        latest, prior = inventory.iloc[-1], inventory.iloc[-2]
        d.metric(
            "Data-center vacancy",
            f"{latest['Vacancy']:.1%}",
            f"{(latest['Vacancy'] - prior['Vacancy']) * 100:+.1f} pp vs {prior['Period']}",
            delta_color="off",
        )
        d.caption(
            f"PCM workbook · {latest['Period']} · inventory {latest['Inventory (MW)']:,.0f} MW "
            f"({latest['Inventory (MW)'] / prior['Inventory (MW)'] - 1:+.0%} vs {prior['Period']})"
        )
    else:
        d.metric("Data-center vacancy", "—")
        d.caption("PCM workbook · unavailable")
    left, middle, right = st.columns(3)
    with left:
        _category_chart(
            ctx,
            inventory,
            "Data center inventory (MW) vs vacancy",
            bars=["Inventory (MW)"],
            lines=["Vacancy"],
            left_title="MW",
            right_title="Vacancy",
            key="supply_dc_inventory",
        )
    with middle:
        _category_chart(
            ctx,
            additions,
            "NAM capacity additions (GW)",
            bars=["Tracked / under construction", "Announced, not yet under construction"],
            left_title="GW",
            stacked=True,
            key="supply_capacity",
        )
        st.caption("Periods marked 'E' are the workbook's estimates, not reported additions.")
    with right:
        _category_chart(
            ctx,
            backlog,
            "Backlog & years to build",
            bars=["Backlog"],
            lines=["Years to build"],
            left_title="Backlog",
            right_title="Years",
            key="supply_backlog_build",
        )


def _price_tile(column, label, series):
    s = series.dropna()
    if s.empty:
        column.metric(label, "—")
        column.caption("PCM workbook · unavailable")
        return
    change = (s.iloc[-1] / s.iloc[-2] - 1) * 100 if len(s) > 1 else np.nan
    column.metric(
        label,
        f"${s.iloc[-1]:,.2f}/GPU-hr",
        None if np.isnan(change) else f"{change:+.1f}% vs prior",
    )
    column.caption(f"PCM workbook (Bloomberg) · {s.index[-1].date()}")


def _category_chart(
    ctx, frame, title, bars, lines=(), left_title="", right_title="", stacked=False, key=""
):
    """Bar/line chart over the workbook's text period labels (2021, 1H25, 2026E, 1Q26 ...)."""
    if frame.empty:
        st.info(f"UNAVAILABLE · {title} is not in the saved workbook.")
        return
    x = frame.iloc[:, 0].astype(str).tolist()
    sources = frame.attrs.get("sources", [])
    fig = make_subplots(specs=[[{"secondary_y": bool(lines)}]])
    for name in bars:
        trace = go.Bar(x=x, y=frame[name], name=name)
        trace.meta = {"sources": sources}
        fig.add_trace(trace, secondary_y=False if lines else None)
    for name in lines:
        trace = go.Scatter(x=x, y=frame[name], name=name, mode="lines+markers")
        trace.meta = {"sources": sources}
        fig.add_trace(trace, secondary_y=True)
    fig.update_layout(title=title, barmode="stack" if stacked else "group")
    fig.update_xaxes(type="category")
    if lines:
        fig.update_yaxes(title_text=left_title, secondary_y=False)
        percent = right_title == "Vacancy"  # saved as fractions with a 0.0% format
        fig.update_yaxes(
            title_text=right_title,
            secondary_y=True,
            showgrid=False,
            tickformat=".1%" if percent else None,
            rangemode="tozero",
        )
    else:
        fig.update_yaxes(title_text=left_title)
    ctx.chart(fig, key=key)
