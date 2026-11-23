"""Recession: independent 17-item checklist, Sahm rule, curve, probabilities and cyclicals."""

import json

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from dashboard.sections.extras import add_reference, checklist, signal_style, workbook_cells
from dashboard.styles.theme import base_table_style
from src.analytics.sectors import recession_spans
from src.analytics.signals import (
    RECESSION_ROWS,
    apply_workbook_fallback,
    checklist_as_of,
    long_run_mean,
    output_gap,
    recession_checklist,
    sahm_rule,
    score,
)
from src.database import store
from src.database.store import ResearchRecord

IDS = [
    "CPIAUCSL",
    "DGS10",
    "DGS2",
    "T10Y3M",
    "RETAILIRSA",
    "DGORDER",
    "A007RL1Q225SBEA",
    "A011RL1Q225SBEA",
    "UNRATE",
    "ICSA",
    "IC4WSA",
    "INDPRO",
    "W875RX1",
    "GDPC1",
    "GDPPOT",
    "M2REAL",
    "CES0500000003",
    "GDP",
    "BAMLH0A0HYM2",
    "UMCSENT",
    "SP500",
    "SAHMREALTIME",
    "RECPROUSM156N",
    "USREC",
]
KPIS = [
    Kpi("SAHMREALTIME", "Sahm rule (real-time)", "{:.2f} pp", "prior", inverse=True),
    Kpi("RECPROUSM156N", "Recession probability", "{:.1f}%", "prior", inverse=True),
    Kpi("T10Y3M", "10Y − 3M curve", "{:+.2f} pp", "yoy_pp"),
    Kpi("UNRATE", "Unemployment", "{:.1f}%", "yoy_pp", inverse=True),
    Kpi("ICSA", "Initial claims", "{:,.0f}", "yoy_pct", inverse=True),
    Kpi("BAMLH0A0HYM2", "HY OAS", "{:.2f}%", "yoy_bp", inverse=True),
]
TABLE = [
    ("SAHMREALTIME", "pp"),
    ("RECPROUSM156N", "pp"),
    ("T10Y3M", "pp"),
    ("UNRATE", "pp"),
    ("ICSA", "pct"),
    ("CPIAUCSL", "pct"),
    ("INDPRO", "pct"),
    ("W875RX1", "pct"),
    ("M2REAL", "pct"),
    ("RETAILIRSA", "pp"),
    ("DGORDER", "pct"),
    ("CES0500000003", "pct"),
    ("UMCSENT", "pp"),
    ("BAMLH0A0HYM2", "pp"),
    ("SP500", "pct"),
]
CROSS_CHECKS = [("recession_0_0", "Sahm rule (Bloomberg SAHMRLRT)", "SAHMREALTIME")]
NOTES = [
    (
        "The independent checklist mirrors the sponsor's 17 Recession-tab items. Each rule is listed "
        "in the table; thresholds come from the sponsor's notes column (e.g., claims > 475k, wage "
        "growth > 3.5%, 10Y − GDP > 0). Score = red ÷ evaluated items, as in the sponsor sheet."
    ),
    (
        "Leading Economic Indicators (Conference Board) and Composite PMI (S&P Global / ISM) are "
        "licensed. They use the sponsor's saved manual flag when a workbook snapshot exists, and "
        "are otherwise UNAVAILABLE and excluded from the denominator."
    ),
    (
        "'Long-run average' means the average of retained history since 2000. Output gap uses CBO "
        "real potential GDP; potential is a projection and is revised."
    ),
    (
        "Credit spreads use ICE BofA HY OAS. FRED now redistributes only about three years of ICE "
        "history, so the rule is change-based (3-month widening > 50 bp) rather than level vs a "
        "long-run average."
    ),
    (
        "Values are current revised observations, not real-time vintages; checklists and the Sahm "
        "calculation are descriptive, not calibrated recession probabilities. The Chauvet-Piger "
        "smoothed probability is published with a lag of about two months."
    ),
    "Shaded areas are NBER recessions (USREC). Observation dates are not release dates.",
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(
        ctx.title, "Independent checklist & analytics"
    )
    with workbook_tab:
        render_workbook(ctx.title, render_section)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        _checklist(ctx, data)
        kpi_row(data, KPIS)
        start = lookback_start("recession")
        _labor(ctx, data, start)
        _curve_and_credit(ctx, data, start)
        _cyclicals(ctx, data, start)
        _reference_dates(ctx, data)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "recession_indicators.csv")
        with st.expander("Workbook vs independent source cross-check"):
            cross_check(ctx, data, ctx.title, CROSS_CHECKS, "recession_xc")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _reference_events():
    with Session(store.engine) as session:
        events = session.scalars(
            select(ResearchRecord).where(ResearchRecord.kind == "historical_event")
        ).all()
        return [json.loads(e.payload) for e in events]


def _reference_dates(ctx, data):
    with st.expander("Checklist at prior recession starts and reference events"):
        dates = {
            f"NBER recession start {begin.date():%Y-%m}": begin
            for begin, _ in recession_spans(data.get("USREC", pd.Series(dtype=float)))
        }
        dates.update(
            {f"{e['name']} ({e['date']})": pd.Timestamp(e["date"]) for e in _reference_events()}
        )
        if not dates:
            st.info(
                "UNAVAILABLE · No USREC history or imported reference events. Import events with "
                "`scripts.import_historical_events`; no dates are invented."
            )
            return
        rows = []
        for label, when in dates.items():
            checks = checklist_as_of(data, when)
            red, evaluated, _ = score(checks)
            row = {"Reference date": label, "Red": red, "Evaluated": evaluated}
            row["Share red (%)"] = red / evaluated * 100 if evaluated else np.nan
            row.update({c.metric: c.row()["signal"] for c in checks})
            rows.append(row)
        frame = pd.DataFrame(rows)
        styled = base_table_style(frame).map(
            signal_style, subset=[c for c in frame.columns if c in RECESSION_ROWS]
        )
        ctx.table_view(styled, hide_index=True, alt="Recession checklist at reference dates")
        st.caption(
            "Rules applied to current revised observations dated on/before each reference date "
            "(history retained since 2000). Not a real-time backtest and not evidence of "
            "predictive power; the sample of recessions is very small."
        )


def _saved_flags(cells):
    """Sponsor F (status) and G (manual red flag) cells keyed by checklist metric."""
    saved = {}
    for metric, row in RECESSION_ROWS.items():
        status, flag = cells.get(f"F{row}"), cells.get(f"G{row}")
        saved[metric] = (status if isinstance(status, str) else None, flag == 1)
    return saved


def _checklist(ctx, data):
    st.subheader("Recession / economic stress checklist")
    st.caption(
        "Rules evaluated automatically from public sources. Sponsor workbook statuses are shown "
        "alongside for comparison and are used only where no independent source exists."
    )
    checks = recession_checklist(data)
    cells = workbook_cells(ctx.title)
    saved = _saved_flags(cells) if cells else {}
    apply_workbook_fallback(
        checks, {k: v for k, v in saved.items() if k.startswith(("Leading", "Composite"))}
    )
    extra = None
    if saved:
        extra = {
            "Workbook status": [
                (saved[c.metric][0] or "—") if c.metric in saved else "—" for c in checks
            ],
            "Workbook flag": [
                ("RED" if saved[c.metric][1] else "Not red") if c.metric in saved else "—"
                for c in checks
            ],
        }
    checklist(ctx, checks, "recession_checklist", "signals", extra)
    if saved:
        sponsor_red = sum(flag for _, flag in saved.values())
        st.caption(
            f"Sponsor saved score: {sponsor_red} of {len(RECESSION_ROWS)} flagged "
            f"({sponsor_red / len(RECESSION_ROWS):.0%}). Saved manual flags may lag current data."
        )


def _labor(ctx, data, start):
    st.subheader("Labor market & recession probabilities")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        official = clip(data.get("SAHMREALTIME", empty), start)
        derived = clip(sahm_rule(data.get("UNRATE", empty)), start)
        series = {"Real-time Sahm (FRED)": official, "DERIVED · current-vintage Sahm": derived}
        fig = line_figure("Sahm rule recession indicator (pp)", series, left_title="pp")
        add_reference(fig, 0.5, "0.50 trigger")
        chart_or_note(
            ctx, fig, [series], "recession_sahm", "Sahm inputs not ingested.", data, start
        )
    with right:
        probability = {"Smoothed probability": clip(data.get("RECPROUSM156N", empty), start)}
        claims = {"Initial claims (4-wk avg, k)": clip(data.get("IC4WSA", empty) / 1000, start)}
        fig = line_figure(
            "Recession probability vs initial claims",
            probability,
            claims,
            "Percent",
            "Thousands",
        )
        chart_or_note(
            ctx,
            fig,
            [probability, claims],
            "recession_probability",
            "Probability/claims not ingested.",
            data,
            start,
        )


def _curve_and_credit(ctx, data, start):
    st.subheader("Yield curve, inflation & credit")
    empty = pd.Series(dtype=float)
    pair = pd.concat(
        [data.get("DGS10", empty), data.get("DGS2", empty)], axis=1, keys=["a", "b"]
    ).dropna()
    left, right = st.columns(2)
    with left:
        curves = {
            "10Y − 2Y": clip(pair["a"] - pair["b"], start),
            "10Y − 3M": clip(data.get("T10Y3M", empty), start),
        }
        fig = line_figure("Treasury curve spreads (pp)", curves, left_title="pp", zero=True)
        chart_or_note(
            ctx, fig, [curves], "recession_curve", "Treasury data not ingested.", data, start
        )
    with right:
        inflation = {
            "CPI-U Y/Y": clip(yoy(data, "CPIAUCSL"), start),
            "Avg hourly earnings Y/Y": clip(yoy(data, "CES0500000003"), start),
        }
        credit = {"HY OAS": clip(data.get("BAMLH0A0HYM2", empty), start)}
        fig = line_figure(
            "Inflation & wages (% Y/Y) vs HY credit spread",
            inflation,
            credit,
            "Percent Y/Y",
            "OAS, percent",
        )
        add_reference(fig, 3.5, "3.5% wage threshold", dash="dot")
        chart_or_note(
            ctx,
            fig,
            [inflation, credit],
            "recession_inflation",
            "Inputs not ingested.",
            data,
            start,
        )


def _cyclicals(ctx, data, start):
    st.subheader("Cyclical components, output gap & money")
    st.caption(
        "Mirrors the sponsor's durable goods / fixed investment / residential investment panels; "
        "dashed lines are averages since 2000."
    )
    empty = pd.Series(dtype=float)
    panels = [
        ("Durable goods orders (% Y/Y)", yoy(data, "DGORDER"), "recession_durables"),
        ("Real fixed investment (% SAAR)", data.get("A007RL1Q225SBEA", empty), "recession_fixed"),
        (
            "Real residential investment (% SAAR)",
            data.get("A011RL1Q225SBEA", empty),
            "recession_residential",
        ),
    ]
    for column, (title, series, key) in zip(st.columns(3), panels, strict=True):
        with column:
            group = {title.split(" (")[0]: clip(series, start)}
            fig = line_figure(title, group, left_title="Percent", zero=True, bars=tuple(group))
            average = long_run_mean(series)
            if pd.notna(average):
                add_reference(fig, average, f"avg {average:+.1f}%")
            chart_or_note(ctx, fig, [group], key, "Component not ingested.", data, start)
    left, right = st.columns(2)
    with left:
        gap = {"Output gap": clip(output_gap(data.get("GDPC1"), data.get("GDPPOT")), start)}
        fig = line_figure(
            "DERIVED · Output gap (% of CBO potential)", gap, left_title="Percent", zero=True
        )
        chart_or_note(ctx, fig, [gap], "recession_gap", "GDPC1/GDPPOT not ingested.", data, start)
    with right:
        growth = {
            "Real M2": clip(yoy(data, "M2REAL"), start),
            "Industrial production": clip(yoy(data, "INDPRO"), start),
            "Real income ex-transfers": clip(yoy(data, "W875RX1"), start),
        }
        fig = line_figure(
            "DERIVED · Money, output & income (% Y/Y)", growth, left_title="Percent", zero=True
        )
        chart_or_note(ctx, fig, [growth], "recession_growth", "Inputs not ingested.", data, start)
