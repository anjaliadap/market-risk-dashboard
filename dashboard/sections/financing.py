"""AI Financing: sponsor Financing Tracker, hyperscaler funding gap, credit spreads, financial
conditions and corporate leverage."""

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
    yoy,
)
from dashboard.sections.extras import add_reference, checklist
from src.analytics.signals import (
    capex_coverage_check,
    funding_gap,
    liquidity_check,
    ratio,
    relative_strength_check,
    spread_vs_average_check,
)

IDS = [
    "BAMLC0A0CM",
    "BAMLC0A4CBBB",
    "BAMLH0A0HYM2",
    "BAMLH0A3HYC",
    "NFCI",
    "DRTSCILM",
    "BCNSDODNS",
    "GDP",
    "USREC",
]
KPIS = [
    Kpi("BAMLC0A0CM", "IG OAS", "{:.2f}%", "yoy_bp", inverse=True),
    Kpi("BAMLC0A4CBBB", "BBB OAS", "{:.2f}%", "yoy_bp", inverse=True),
    Kpi("BAMLH0A0HYM2", "HY OAS", "{:.2f}%", "yoy_bp", inverse=True),
    Kpi("BAMLH0A3HYC", "CCC & lower OAS", "{:.2f}%", "yoy_bp", inverse=True),
    Kpi("NFCI", "Financial conditions (NFCI)", "{:+.2f}", "yoy_abs", inverse=True),
    Kpi("DRTSCILM", "Banks tightening C&I", "{:+.1f}%", "prior", inverse=True),
]
TABLE = [
    ("BAMLC0A0CM", "pp"),
    ("BAMLC0A4CBBB", "pp"),
    ("BAMLH0A0HYM2", "pp"),
    ("BAMLH0A3HYC", "pp"),
    ("NFCI", "pp"),
    ("DRTSCILM", "pp"),
    ("BCNSDODNS", "pct"),
]
COMPANY_RATIOS = {
    "AMZN": "financing_0_2",
    "GOOGL": "financing_0_3",
    "META": "financing_0_4",
    "Combined": "financing_0_5",
}
NOTES = [
    (
        "The Financing Tracker reproduces the sponsor's four warning items. Company-specific items "
        "(capex vs CFOps, HY Tech − IG, ORCL/CRWV relative strength) come from the sponsor's saved "
        "Bloomberg data, reported quarters only. Where the workbook is unavailable, the HY Tech "
        "item falls back to the broad FRED HY − IG OAS, labelled as a proxy."
    ),
    (
        "'Lower liquidity / AI lab IPO delays' cannot be measured directly. The proxy flags when "
        "the Chicago Fed NFCI is more than 0.25 SD tighter than a year ago and banks are net "
        "tightening C&I lending standards (SLOOS, large and middle-market firms). IPO timing "
        "needs analyst judgment."
    ),
    (
        "ICE BofA option-adjusted spreads: FRED redistributes about three years of history, so "
        "percentiles and averages refer to that window only."
    ),
    (
        "Funding gap = combined hyperscaler capex − cash flow from operations per quarter (USD as "
        "saved by the sponsor). Positive values must be met from cash balances, debt or equity."
    ),
    (
        "Nonfinancial corporate debt / GDP uses Z.1 debt securities and loans (millions, converted "
        "to billions) over nominal GDP (billions, SAAR)."
    ),
    "Shaded areas are NBER recessions (USREC). Observation dates are not release dates.",
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(
        ctx.title, "Financing tracker & analytics"
    )
    with workbook_tab:
        render_workbook(ctx.title, render_section)
        if workbook_section(ctx.title) is not None:
            _workbook_analytics(ctx)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        _tracker(ctx, data)
        kpi_row(data, KPIS)
        start = lookback_start("financing", "5Y")
        _credit(ctx, data, start)
        _conditions(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "financing_indicators.csv")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _hy_ig(data):
    empty = pd.Series(dtype=float)
    pair = pd.concat(
        [data.get("BAMLH0A0HYM2", empty), data.get("BAMLC0A0CM", empty)], axis=1, keys=["h", "i"]
    ).dropna()
    return pair["h"] - pair["i"]


def _tracker(ctx, data):
    st.subheader("Financing tracker")
    title = ctx.title
    checks = [
        capex_coverage_check(workbook_series(title, "financing_0_5")),
        spread_vs_average_check(
            workbook_series(title, "financing_2_0"),
            workbook_series(title, "financing_2_1"),
            "Workbook (saved HY Tech − IG)",
            independent=_hy_ig(data),
        ),
        relative_strength_check(
            {
                "ORCL": workbook_series(title, "financing_3_0"),
                "CRWV": workbook_series(title, "financing_3_1"),
            }
        ),
        liquidity_check(data.get("NFCI"), data.get("DRTSCILM")),
    ]
    checklist(ctx, checks, "financing_tracker", "warnings")


def _workbook_analytics(ctx):
    st.subheader("Workbook-derived funding analysis")
    st.caption("Reported quarters only; forward estimates excluded.")
    capex = workbook_series(ctx.title, "financing_1_0")
    cfo = workbook_series(ctx.title, "financing_1_3")
    gap = funding_gap(capex, cfo)
    rows = []
    for company, series_id in COMPANY_RATIOS.items():
        s = workbook_series(ctx.title, series_id)
        if s.empty:
            rows.append({"Company": company, "Status": "UNAVAILABLE · saved points missing"})
            continue
        rows.append(
            {
                "Company": company,
                "Quarter": s.index[-1].date(),
                "TTM capex / CFOps (%)": s.iloc[-1] * 100,
                "Four quarters earlier (%)": s.iloc[-5] * 100 if len(s) > 4 else float("nan"),
                "Status": "RED" if s.iloc[-1] > 1 else "AVAILABLE",
            }
        )
    ctx.table_view(pd.DataFrame(rows), hide_index=True)
    a, b = st.columns(2)
    derived_metric(a, "Latest quarterly funding gap", gap, "${:,.0f}", "capex − CFOps, saved USD")
    derived_metric(
        b,
        "Trailing four-quarter funding gap",
        gap.rolling(4).sum() if len(gap) >= 4 else None,
        "${:,.0f}",
        "sum of last four reported quarters",
    )
    if len(gap):
        fig = line_figure(
            "DERIVED · Combined hyperscaler funding gap (capex − CFOps)",
            {"Quarterly gap": gap},
            left_title="Saved workbook USD",
            zero=True,
            bars=("Quarterly gap",),
        )
        ctx.chart(fig, key="financing_gap")
        st.caption("Above zero: quarterly capex exceeded operating cash flow.")


def _credit(ctx, data, start):
    st.subheader("Credit spreads")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        series = {
            "IG": clip(data.get("BAMLC0A0CM", empty), start),
            "BBB": clip(data.get("BAMLC0A4CBBB", empty), start),
            "HY": clip(data.get("BAMLH0A0HYM2", empty), start),
        }
        ccc = {"CCC & lower": clip(data.get("BAMLH0A3HYC", empty), start)}
        fig = line_figure(
            "ICE BofA option-adjusted spreads (%)", series, ccc, "IG / BBB / HY, %", "CCC, %"
        )
        chart_or_note(
            ctx, fig, [series, ccc], "financing_oas", "OAS series not ingested.", data, start
        )
    with right:
        diff = _hy_ig(data)
        series = {"HY − IG": clip(diff * 100, start)}
        fig = line_figure(
            "DERIVED · HY minus IG spread (bp) — broad-market analogue of sponsor's HY Tech − IG",
            series,
            left_title="Basis points",
        )
        if len(diff):
            add_reference(fig, float(diff.mean() * 100), "average of retained history", dash="dot")
        chart_or_note(
            ctx, fig, [series], "financing_hy_ig", "OAS series not ingested.", data, start
        )


def _conditions(ctx, data, start):
    st.subheader("Financial conditions & corporate leverage")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        nfci = {"NFCI": clip(data.get("NFCI", empty), start)}
        standards = {"Net % banks tightening C&I": clip(data.get("DRTSCILM", empty), start)}
        fig = line_figure(
            "Financial conditions vs bank lending standards",
            nfci,
            standards,
            "NFCI (positive = tighter)",
            "Net percent",
            zero=True,
        )
        chart_or_note(
            ctx, fig, [nfci, standards], "financing_nfci", "NFCI/SLOOS not ingested.", data, start
        )
    with right:
        leverage = ratio(data.get("BCNSDODNS", empty), data.get("GDP", empty), 45, 100 / 1000)
        series = {"Debt / GDP": clip(leverage, start)}
        growth = {"Debt growth Y/Y": clip(yoy(data, "BCNSDODNS"), start)}
        fig = line_figure(
            "DERIVED · Nonfinancial corporate debt (% of GDP)",
            series,
            growth,
            "Percent of GDP",
            "Percent Y/Y",
        )
        chart_or_note(
            ctx,
            fig,
            [series, growth],
            "financing_leverage",
            "Z.1 debt/GDP not ingested.",
            data,
            start,
        )
