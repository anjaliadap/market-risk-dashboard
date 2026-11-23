"""VIX & Options: volatility regime, term structure, implied vs realized, cross-asset vol, and
analytics on the sponsor's saved options-activity series (VIX calls, S&P puts, put/call)."""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    Kpi,
    chart_or_note,
    clip,
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
    workbook_section,
    workbook_series,
)
from dashboard.sections.extras import add_reference, checklist
from src.analytics.sectors import zscore
from src.analytics.signals import (
    Check,
    days_since,
    implied_minus_realized,
    last,
    percentile_rank,
    realized_volatility,
    term_structure,
    vol_regime,
)

IDS = ["VIXCLS", "VXVCLS", "VXNCLS", "OVXCLS", "GVZCLS", "SP500", "BAMLH0A0HYM2", "USREC"]
KPIS = [
    Kpi("VIXCLS", "VIX", "{:.2f}", "prior", inverse=True),
    Kpi("VXVCLS", "VIX3M", "{:.2f}", "prior", inverse=True),
    Kpi("VXNCLS", "Nasdaq-100 vol (VXN)", "{:.2f}", "prior", inverse=True),
    Kpi("OVXCLS", "Crude oil vol (OVX)", "{:.2f}", "prior", inverse=True),
    Kpi("GVZCLS", "Gold vol (GVZ)", "{:.2f}", "prior", inverse=True),
]
TABLE = [
    ("VIXCLS", "pp"),
    ("VXVCLS", "pp"),
    ("VXNCLS", "pp"),
    ("OVXCLS", "pp"),
    ("GVZCLS", "pp"),
    ("SP500", "pct"),
    ("BAMLH0A0HYM2", "pp"),
]
WORKBOOK = {
    "vix_and_options_0_0": ("VIX call volume", "contracts / week"),
    "vix_and_options_1_0": ("S&P 500 put volume", "contracts / week"),
    "vix_and_options_2_0": ("CBOE put/call ratio", "ratio"),
}
NOTES = [
    (
        "VIX regimes: Calm < 15, Normal 15–20, Elevated 20–30, Stress ≥ 30. These are conventional "
        "descriptive bands, not forecasts."
    ),
    (
        "Term structure = VIX ÷ VIX3M on common dates. Above 1.0 (backwardation) means near-term "
        "implied volatility exceeds 3-month implied volatility, typical of acute stress."
    ),
    (
        "Implied − realized = VIX minus 21-session annualized close-to-close volatility of the S&P "
        "500 price index. A rough variance-risk-premium proxy; not a traded variance swap."
    ),
    (
        "Options-activity analytics (percentiles, z-scores, 4-week averages) are computed on the "
        "sponsor's saved weekly Bloomberg series. CBOE put/call and MOVE have no free licensed "
        "feed connected, so they remain workbook-only."
    ),
    "Shaded areas are NBER recessions (USREC). FRED VIX series are daily closes.",
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
        if workbook_section(ctx.title) is not None:
            _workbook_analytics(ctx)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        _signal_board(ctx, data)
        kpi_row(data, KPIS)
        start = lookback_start("vix", "5Y")
        _regime(ctx, data, start)
        _structure(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "vix_indicators.csv")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _signal_board(ctx, data):
    st.subheader("Volatility signal board")
    st.caption("Descriptive stress signals; RED = condition typical of market stress is present.")
    empty = pd.Series(dtype=float)
    vix = data.get("VIXCLS", empty)
    checks = []

    level, as_of = last(vix)
    c = Check("VIX regime", "Stress (≥ 30)", "VIX close at or above 30", source="FRED: VIXCLS")
    if not np.isnan(level):
        c.red, c.status, c.as_of = level >= 30, vol_regime(level), as_of
        since = days_since(vix, 30)
        c.reading = f"{level:.2f}" + (f"; {since} days since last ≥ 30 close" if since else "")
    checks.append(c)

    ratio = term_structure(vix, data.get("VXVCLS", empty))
    now, as_of = last(ratio)
    c = Check(
        "VIX term structure",
        "Backwardation (> 1.0)",
        "VIX ÷ VIX3M above 1.0",
        source="FRED: VIXCLS, VXVCLS",
    )
    if not np.isnan(now):
        c.red, c.as_of = now > 1.0, as_of
        c.status = "Backwardation" if c.red else "Contango"
        c.reading = f"{now:.2f}"
    checks.append(c)

    rank = percentile_rank(vix, start=pd.Timestamp.today() - pd.DateOffset(years=1))
    c = Check(
        "VIX vs trailing year",
        "Top decile",
        "Latest VIX at or above the 90th percentile of the trailing 12 months",
        source="FRED: VIXCLS",
    )
    if not np.isnan(rank):
        c.red, c.as_of = rank >= 90, last(vix)[1]
        c.status = f"{rank:.0f}th percentile"
        c.reading = f"{level:.2f}"
    checks.append(c)

    spread = implied_minus_realized(vix, data.get("SP500", empty))
    now, as_of = last(spread)
    c = Check(
        "Implied minus realized",
        "Negative premium",
        "VIX below 21-session realized S&P 500 volatility (realized vol outrunning implied)",
        source="FRED: VIXCLS, SP500",
    )
    if not np.isnan(now):
        c.red, c.as_of = now < 0, as_of
        c.status = "Negative premium" if c.red else "Positive premium"
        c.reading = f"{now:+.2f} vol pts"
    checks.append(c)

    pc = workbook_series(ctx.title, "vix_and_options_2_0")
    now, as_of = last(pc)
    c = Check(
        "CBOE put/call ratio",
        "Top decile (fear)",
        "Saved weekly put/call at or above its 90th percentile since 2006",
        source="Workbook (saved)",
    )
    if not np.isnan(now):
        rank = percentile_rank(pc)
        c.red, c.as_of = rank >= 90, as_of
        c.status = f"{rank:.0f}th percentile"
        c.reading = f"{now:.2f}"
    checks.append(c)
    checklist(ctx, checks, "vix_signal_board", "stress signals")


def _regime(ctx, data, start):
    st.subheader("Volatility regime")
    empty = pd.Series(dtype=float)
    vix = data.get("VIXCLS", empty)
    realized = realized_volatility(data.get("SP500", empty))
    a, b, c = st.columns(3)
    level, as_of = last(vix)
    a.metric("VIX regime", vol_regime(level))
    a.caption(f"DERIVED · Calm < 15 ≤ Normal < 20 ≤ Elevated < 30 ≤ Stress · {as_of or '—'}")
    derived_metric(b, "S&P 21-day realized vol", realized, "{:.1f}%", "annualized percent")
    score = zscore(vix)
    c.metric("VIX z-score (retained history)", "—" if np.isnan(score) else f"{score:+.2f}")
    c.caption("DERIVED · standard deviations from the mean since 2000")
    left, right = st.columns(2)
    with left:
        series = {"VIX": clip(vix, start), "S&P 500 realized vol (21d)": clip(realized, start)}
        fig = line_figure("Implied vs realized volatility", series, left_title="Annualized %")
        for y, label in ((15, "15"), (20, "20"), (30, "30 stress")):
            add_reference(fig, y, label, dash="dot")
        chart_or_note(ctx, fig, [series], "vix_regime", "VIX/S&P 500 not ingested.", data, start)
    with right:
        spread = {
            "VIX − realized": clip(implied_minus_realized(vix, data.get("SP500", empty)), start)
        }
        fig = line_figure(
            "DERIVED · Implied minus realized volatility",
            spread,
            left_title="Vol points",
            zero=True,
        )
        chart_or_note(ctx, fig, [spread], "vix_premium", "Inputs not ingested.", data, start)


def _structure(ctx, data, start):
    st.subheader("Term structure & cross-asset volatility")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        ratio = {"VIX ÷ VIX3M": clip(term_structure(data.get("VIXCLS"), data.get("VXVCLS")), start)}
        fig = line_figure("DERIVED · VIX term structure", ratio, left_title="Ratio")
        add_reference(fig, 1.0, "1.0 = flat; above = backwardation")
        chart_or_note(ctx, fig, [ratio], "vix_term", "VIX/VIX3M not ingested.", data, start)
    with right:
        series = {
            "VIX (S&P 500)": clip(data.get("VIXCLS", empty), start),
            "VXN (Nasdaq-100)": clip(data.get("VXNCLS", empty), start),
            "OVX (crude oil)": clip(data.get("OVXCLS", empty), start),
            "GVZ (gold)": clip(data.get("GVZCLS", empty), start),
        }
        fig = line_figure("Cross-asset implied volatility", series, left_title="Index")
        chart_or_note(
            ctx, fig, [series], "vix_cross", "Volatility indices not ingested.", data, start
        )


def _workbook_analytics(ctx):
    st.subheader("Workbook-derived options analytics")
    st.caption(
        "Computed from the sponsor's saved weekly Bloomberg series. 'Current' reference lines in "
        "the charts above are the sponsor's saved fixed-row values."
    )
    rows = []
    for series_id, (label, unit) in WORKBOOK.items():
        s = workbook_series(ctx.title, series_id)
        if s.empty:
            rows.append({"Series": label, "Status": "UNAVAILABLE · no saved points"})
            continue
        trailing = s.loc[s.index[-1] - pd.DateOffset(years=1) :]
        rows.append(
            {
                "Series": label,
                "Latest": s.iloc[-1],
                "Units": unit,
                "Week ending": s.index[-1].date(),
                "4-week average": s.tail(4).mean(),
                "1Y average": trailing.mean(),
                "Percentile (full history)": percentile_rank(s),
                "Percentile (1Y)": percentile_rank(trailing),
                "Z-score (full history)": zscore(s),
                "Status": "AVAILABLE",
            }
        )
    ctx.table_view(pd.DataFrame(rows), hide_index=True)
    pc = workbook_series(ctx.title, "vix_and_options_2_0")
    if len(pc) >= 8:
        smooth = {"Put/call (4-wk avg)": pc.rolling(4).mean(), "Put/call (weekly)": pc}
        fig = line_figure("DERIVED · CBOE put/call ratio, smoothed", smooth, left_title="Ratio")
        for q, label in ((0.1, "10th pct"), (0.9, "90th pct")):
            add_reference(fig, float(pc.quantile(q)), label, dash="dot")
        ctx.chart(fig, key="vix_workbook_pc")
