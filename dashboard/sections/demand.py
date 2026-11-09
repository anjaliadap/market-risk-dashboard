"""AI Demand: sponsor Demand Tracker, hyperscaler sales vs capex, US productivity, the
semiconductor cycle and AI-related investment."""

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
    yoy,
)
from dashboard.sections.extras import add_reference, analyst_log, checklist
from src.analytics.signals import (
    annualized_growth,
    momentum,
    peak_status,
    period_cagr,
    productivity_check,
    ratio,
    sales_vs_capex,
    sales_vs_capex_check,
    semiconductor_check,
)

IDS = [
    "OPHNFB",
    "PRS85006092",
    "ULCNFB",
    "IPG3344S",
    "CAPUTLG3344S",
    "A34SNO",
    "A34SVS",
    "PCU33443344",
    "A679RL1Q225SBEA",
    "A679RC1Q027SBEA",
    "GDP",
    "USREC",
]
KPIS = [
    Kpi("OPHNFB", "Productivity (output/hour)", "{:.1f}", "yoy_pct"),
    Kpi("PRS85006092", "Productivity, Q/Q SAAR", "{:+.1f}%", "prior"),
    Kpi("ULCNFB", "Unit labor costs", "{:.1f}", "yoy_pct", inverse=True),
    Kpi("IPG3344S", "Semiconductor output", "{:.1f}", "yoy_pct"),
    Kpi("CAPUTLG3344S", "Semis capacity use", "{:.1f}%", "yoy_pp"),
    Kpi("A679RL1Q225SBEA", "Real IT equip & software inv.", "{:+.1f}%", "prior"),
]
TABLE = [
    ("OPHNFB", "pct"),
    ("PRS85006092", "pp"),
    ("ULCNFB", "pct"),
    ("IPG3344S", "pct"),
    ("CAPUTLG3344S", "pp"),
    ("A34SNO", "pct"),
    ("A34SVS", "pct"),
    ("PCU33443344", "pct"),
    ("A679RL1Q225SBEA", "pp"),
    ("A679RC1Q027SBEA", "pct"),
]
# Company: (sales series, sales label, capex+R&D series, FCF margin series). Cloud segment growth
# is used where the sponsor maps it (closest available proxy for AI sales); META uses revenue.
COMPANIES = {
    "AMZN": ("demand_0_3", "AWS", "demand_0_4", "demand_1_2", "demand_0_2"),
    "GOOGL": ("demand_2_3", "Google Cloud", "demand_2_4", "demand_3_2", "demand_2_2"),
    "META": ("demand_4_2", "Revenue", "demand_4_3", "demand_5_2", "demand_4_2"),
}
PERIODS = [
    ("2000 → 2007-Q4", "2000-01-01", "2007-10-01"),
    ("2007-Q4 → 2019-Q4", "2007-10-01", "2019-10-01"),
    ("2019-Q4 → latest", "2019-10-01", None),
    ("2022-Q4 (gen-AI era) → latest", "2022-10-01", None),
]
NOTES = [
    (
        "The Demand Tracker reproduces the sponsor's three warning items as explicit rules. Sales "
        "vs capex uses the sponsor's saved reported quarters only (forward estimates excluded); "
        "cloud segment growth stands in for AI sales where mapped. Cloud revenue is not "
        "AI-specific revenue."
    ),
    (
        "Productivity is BLS nonfarm business output per hour. Period growth rates are compound "
        "annual rates between the quarters shown. Comparing the post-2022 period with 2007–2019 "
        "is descriptive: it cannot isolate AI from cyclical, measurement or composition effects."
    ),
    (
        "Semiconductor billings (SIA/WSTS) are licensed. The independent proxy is Fed industrial "
        "production for NAICS 3344 (semiconductors and electronic components, real output index), "
        "plus Census M3 orders/shipments for computers and electronic products (nominal). Enter "
        "SIA's monthly 3-month-average billings in the analyst log for direct tracking."
    ),
    (
        "Book-to-bill = new orders ÷ shipments (3-month averages). Above 1.0 means orders are "
        "outrunning deliveries. Momentum peaks are reported descriptively over the last 24 months."
    ),
    (
        "Information processing equipment & software investment share = nominal investment ÷ "
        "nominal GDP, both SAAR in billions."
    ),
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(
        ctx.title, "Demand tracker & analytics"
    )
    companies = _company_signals(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
        if workbook_section(ctx.title) is not None:
            _workbook_analytics(ctx, companies)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        st.subheader("Demand tracker")
        checklist(
            ctx,
            [
                sales_vs_capex_check({k: v["signal"] for k, v in companies.items()}),
                productivity_check(data.get("OPHNFB")),
                semiconductor_check(data.get("IPG3344S"), data.get("A34SVS")),
            ],
            "demand_tracker",
            "warnings",
        )
        kpi_row(data, KPIS)
        start = lookback_start("demand", "20Y")
        _productivity(ctx, data, start)
        _semiconductors(ctx, data, start)
        _investment(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "demand_indicators.csv")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _company_signals(title):
    out = {}
    for company, (sales_id, sales_label, capex_id, fcf_id, revenue_id) in COMPANIES.items():
        sales = workbook_series(title, sales_id)
        capex = workbook_series(title, capex_id)
        out[company] = {
            "sales_label": sales_label,
            "sales": sales,
            "capex": capex,
            "revenue": workbook_series(title, revenue_id),
            "fcf": workbook_series(title, fcf_id),
            "signal": sales_vs_capex(sales, capex),
        }
    return out


def _workbook_analytics(ctx, companies):
    st.subheader("Workbook-derived hyperscaler comparison")
    st.caption("Latest reported quarter from saved sponsor data; forward estimates are excluded.")
    rows = []
    gaps = {}
    for company, item in companies.items():
        signal = item["signal"]
        if signal is None:
            rows.append({"Company": company, "Status": "UNAVAILABLE · saved points missing"})
            continue
        fcf = item["fcf"]
        rows.append(
            {
                "Company": company,
                "Quarter": signal["as_of"],
                "Sales measure": item["sales_label"],
                "Sales growth (TTM Y/Y, %)": signal["revenue"] * 100,
                "Prior quarter (%)": signal["revenue_prior"] * 100,
                "Capex + R&D growth (%)": signal["capex"] * 100,
                "Capex − sales growth (pp)": (signal["capex"] - signal["revenue"]) * 100,
                "FCF margin (TTM, %)": fcf.iloc[-1] * 100 if len(fcf) else np.nan,
                "Status": "RED" if signal["red"] else "AVAILABLE",
            }
        )
        pair = pd.concat([item["capex"], item["sales"]], axis=1, keys=["c", "s"]).dropna()
        gaps[company] = (pair["c"] - pair["s"]) * 100
    ctx.table_view(pd.DataFrame(rows), hide_index=True)
    if any(len(g) for g in gaps.values()):
        fig = line_figure(
            "DERIVED · Capex+R&D growth minus sales growth (pp, reported quarters)",
            gaps,
            left_title="Percentage points",
            zero=True,
        )
        ctx.chart(fig, key="demand_gap")
        st.caption("Above zero: investment growing faster than the sales it is meant to support.")


def _productivity(ctx, data, start):
    st.subheader("US productivity: accelerating or slowing?")
    empty = pd.Series(dtype=float)
    productivity = data.get("OPHNFB", empty)
    a, b, c, d = st.columns(4)
    derived_metric(a, "Productivity Y/Y", yoy(data, "OPHNFB"), "{:+.1f}%", "percent Y/Y")
    derived_metric(b, "2-year annualized", annualized_growth(productivity, 2), "{:+.1f}%", "CAGR")
    derived_metric(c, "5-year annualized", annualized_growth(productivity, 5), "{:+.1f}%", "CAGR")
    era = period_cagr(productivity, "2022-10-01") if len(productivity) else np.nan
    base = period_cagr(productivity, "2007-10-01", "2019-10-01") if len(productivity) else np.nan
    d.metric(
        "Gen-AI era vs 2007–19",
        "—" if np.isnan(era) or np.isnan(base) else f"{era - base:+.2f} pp",
        help="Compound annual productivity growth since 2022-Q4 minus the 2007-Q4 → 2019-Q4 rate.",
    )
    d.caption("DERIVED · descriptive, not causal")
    left, right = st.columns(2)
    with left:
        bars = {"Q/Q annualized": clip(data.get("PRS85006092", empty), start)}
        lines = {
            "Y/Y": clip(yoy(data, "OPHNFB"), start),
            "2-year annualized": clip(annualized_growth(productivity, 2), start),
        }
        fig = line_figure(
            "Nonfarm business productivity growth (%)",
            {**bars, **lines},
            left_title="Percent",
            zero=True,
            bars=tuple(bars),
        )
        chart_or_note(
            ctx,
            fig,
            [bars, lines],
            "demand_productivity",
            "BLS productivity not ingested.",
            data,
            start,
        )
    with right:
        series = {
            "Productivity Y/Y": clip(yoy(data, "OPHNFB"), start),
            "Unit labor costs Y/Y": clip(yoy(data, "ULCNFB"), start),
        }
        fig = line_figure(
            "Productivity vs unit labor costs (% Y/Y)", series, left_title="Percent", zero=True
        )
        chart_or_note(ctx, fig, [series], "demand_ulc", "BLS series not ingested.", data, start)
    rows = (
        [
            {
                "Period": label,
                "Annualized productivity growth (%)": period_cagr(productivity, a_, b_),
            }
            for label, a_, b_ in PERIODS
        ]
        if len(productivity)
        else []
    )
    if rows:
        ctx.table_view(pd.DataFrame(rows), hide_index=True)


def _semiconductors(ctx, data, start):
    st.subheader("Semiconductor cycle: at or near a peak?")
    empty = pd.Series(dtype=float)
    output_momentum = momentum(data.get("IPG3344S", empty))
    peak = peak_status(output_momentum)
    a, b, c = st.columns(3)
    derived_metric(a, "Semis output Y/Y (3MMA)", output_momentum, "{:+.1f}%", "percent Y/Y")
    if peak:
        b.metric(
            "24-month momentum peak",
            f"{peak['peak']:+.1f}%",
            f"{peak['drawdown']:+.1f} pp since",
            delta_color="normal",
        )
        b.caption(
            f"DERIVED · peak {peak['peak_date']} · "
            + (
                "at peak"
                if peak["observations_since_peak"] == 0
                else f"{peak['observations_since_peak']} months past"
            )
        )
    else:
        b.metric("24-month momentum peak", "—")
        b.caption("DERIVED · inputs unavailable")
    book = ratio(
        data.get("A34SNO", empty).rolling(3).mean(), data.get("A34SVS", empty).rolling(3).mean()
    )
    derived_metric(c, "Book-to-bill (computers & electronics)", book, "{:.2f}", "ratio, 3MMA")
    left, right = st.columns(2)
    with left:
        series = {
            "Semis output (IP 3344)": clip(output_momentum, start),
            "Computer & electronic shipments": clip(momentum(data.get("A34SVS", empty)), start),
            "Computer & electronic new orders": clip(momentum(data.get("A34SNO", empty)), start),
        }
        fig = line_figure(
            "DERIVED · Semiconductor momentum (% Y/Y, 3-month average)",
            series,
            left_title="Percent",
            zero=True,
        )
        chart_or_note(
            ctx, fig, [series], "demand_semis", "Semiconductor proxies not ingested.", data, start
        )
    with right:
        utilization = {"Capacity utilization": clip(data.get("CAPUTLG3344S", empty), start)}
        prices = {"Semis PPI Y/Y": clip(yoy(data, "PCU33443344"), start)}
        fig = line_figure(
            "Semis capacity utilization vs producer prices",
            utilization,
            prices,
            "Percent of capacity",
            "PPI, % Y/Y",
        )
        chart_or_note(
            ctx,
            fig,
            [utilization, prices],
            "demand_semis_util",
            "Inputs not ingested.",
            data,
            start,
        )
    with st.expander("Semiconductor billings (SIA/WSTS) · analyst-sourced"):
        analyst_log(ctx, "semis_billings", "demand_sia")


def _investment(ctx, data, start):
    st.subheader("AI-related business investment")
    empty = pd.Series(dtype=float)
    share = ratio(data.get("A679RC1Q027SBEA", empty), data.get("GDP", empty), 45, 100.0)
    left, right = st.columns(2)
    with left:
        growth = {"Real growth (% SAAR)": clip(data.get("A679RL1Q225SBEA", empty), start)}
        fig = line_figure(
            "Real information processing equipment & software investment",
            growth,
            left_title="Percent, SAAR",
            zero=True,
            bars=tuple(growth),
        )
        chart_or_note(
            ctx, fig, [growth], "demand_invest", "BEA investment not ingested.", data, start
        )
    with right:
        series = {"Share of GDP": clip(share, start)}
        fig = line_figure(
            "DERIVED · IT equipment & software investment (% of nominal GDP)",
            series,
            left_title="Percent of GDP",
        )
        if len(share.dropna()):
            add_reference(fig, float(share.dropna().mean()), "average", dash="dot")
        chart_or_note(
            ctx, fig, [series], "demand_share", "Investment/GDP not ingested.", data, start
        )
