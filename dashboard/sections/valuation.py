"""Valuation: rate-relative earnings yield, aggregate market value, profits and P/E models."""

import numpy as np
import pandas as pd
import plotly.express as px
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
    workbook_cell,
)
from src.analytics.core import justified_pe
from src.analytics.sectors import (
    bands,
    earnings_yield,
    history_percentile,
    implied_growth,
    justified_pe_grid,
    ordinal,
    pe_for_premium,
    scaled_ratio,
    zscore,
)

IDS = ["DGS10", "DFII10", "T10YIE", "NCBEILQ027S", "CP", "GDP", "SP500", "USREC"]
KPIS = [
    Kpi("DGS10", "10Y Treasury", "{:.2f}%", "yoy_bp"),
    Kpi("DFII10", "10Y TIPS real yield", "{:.2f}%", "yoy_bp"),
    Kpi("T10YIE", "10Y breakeven", "{:.2f}%", "yoy_bp"),
    Kpi("SP500", "S&P 500", "{:,.0f}", "yoy_pct"),
]
TABLE = [
    ("DGS10", "pp"),
    ("DFII10", "pp"),
    ("T10YIE", "pp"),
    ("SP500", "pct"),
    ("NCBEILQ027S", "pct"),
    ("CP", "pct"),
    ("GDP", "pct"),
]
NOTES = [
    (
        "Earnings yield = 100 / P-E. The P/E input defaults to the sponsor workbook's saved "
        "earnings-yield-implied P/E (Valuation!F11 = 1/F9) when a validated snapshot exists; the "
        "trailing/forward definition is the sponsor's. Otherwise it must be entered."
    ),
    (
        "Earnings-yield gaps are simple differences, not a modeled equity risk premium. The real-yield "
        "gap is more internally consistent because earnings grow with inflation; both ignore growth."
    ),
    (
        "Implied growth inverts P/E = payout / (r − g): g = r − payout / P-E. Perpetual-growth model; "
        "results are highly sensitive to r and payout."
    ),
    (
        "Market value / GDP uses Z.1 nonfinancial corporate equities at market value (millions USD, "
        "includes estimated closely held equity, excludes financial firms) over nominal GDP (billions "
        "USD SAAR), converted to common units. It is not the Wilshire 5000 'Buffett indicator'."
    ),
    "Corporate profits are BEA after-tax profits without IVA/CCAdj (billions SAAR) over nominal GDP.",
    "FRED's S&P 500 history is limited to ~10 years by license; index multiples are not on FRED.",
    (
        "Bands are full-sample mean ± 1 standard deviation over retained history and are context, "
        "not mean-reversion forecasts."
    ),
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        kpi_row(data, KPIS)
        _rate_relative(ctx, data)
        start = lookback_start("valuation", default="Max")
        _aggregate(ctx, data, start)
        _models(ctx, data)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "valuation_indicators.csv")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _workbook_pe():
    pe = workbook_cell("Valuation", "F11")
    if pe is None:
        ey = workbook_cell("Valuation", "F9")
        pe = 1 / ey if ey and ey > 0 else None
    return pe if pe and 0 < pe < 200 else None


def _rate_relative(ctx, data):
    st.subheader("Equity yield vs rates")
    saved = _workbook_pe()
    a, b, c = st.columns(3)
    pe = a.number_input(
        "Index P/E" + (" (workbook saved value)" if saved else " · ANALYST INPUT"),
        min_value=0.0,
        max_value=200.0,
        value=round(saved, 2) if saved else None,
        step=0.1,
        placeholder="Enter P/E",
        key="valuation_pe",
    )
    cost = b.number_input("Assumed cost of equity (%)", value=9.0, step=0.25, key="valuation_cost")
    payout = c.slider("Assumed payout ratio", 0.0, 1.0, 0.40, 0.05, key="valuation_payout")
    if not pe:
        st.info(
            "Enter an index P/E (or import the workbook) to compute earnings-yield gaps and "
            "implied growth. No multiple is assumed."
        )
        return
    ey = earnings_yield(pe)
    nominal = data.get("DGS10", pd.Series(dtype=float)).dropna()
    real = data.get("DFII10", pd.Series(dtype=float)).dropna()
    cols = st.columns(4)
    cols[0].metric("Earnings yield", f"{ey:.2f}%", help="100 / P-E")
    cols[1].metric(
        "EY − 10Y nominal",
        f"{(ey - nominal.iloc[-1]) * 100:+,.0f} bp" if len(nominal) else "—",
        help="Simple Fed-model gap; DGS10 latest",
    )
    cols[2].metric(
        "EY − 10Y real",
        f"{(ey - real.iloc[-1]) * 100:+,.0f} bp" if len(real) else "—",
        help="Earnings yield minus 10Y TIPS yield",
    )
    growth = implied_growth(pe, cost, payout)
    cols[3].metric("Implied perpetual growth", f"{growth:.2f}%" if np.isfinite(growth) else "—")
    st.caption(
        f"DERIVED from P/E {pe:.2f}"
        + (
            " (workbook saved)"
            if saved and abs(pe - round(saved, 2)) < 1e-9
            else " (analyst input)"
        )
        + f", cost of equity {cost:.2f}% and payout {payout:.0%} (assumptions)."
    )
    if len(real):
        premiums = [2.0, 3.0, 4.0, 5.0, 6.0]
        table = pd.DataFrame(
            {
                "Premium over 10Y real (%)": premiums,
                "Required earnings yield (%)": [real.iloc[-1] + p for p in premiums],
                "Consistent P/E": [pe_for_premium(real.iloc[-1], p) for p in premiums],
            }
        )
        table["Current P/E vs consistent (%)"] = (pe / table["Consistent P/E"] - 1) * 100
        st.markdown("**P/E consistent with a given premium over the real yield**")
        ctx.table_view(table, hide_index=True)


def _aggregate(ctx, data, start):
    st.subheader("Aggregate valuation & profitability")
    empty = pd.Series(dtype=float)
    market_gdp = (
        scaled_ratio(data["NCBEILQ027S"], data["GDP"], 0.1, 45)
        if {"NCBEILQ027S", "GDP"} <= data.keys()
        else empty
    )
    profits_gdp = (
        scaled_ratio(data["CP"], data["GDP"], 100, 45) if {"CP", "GDP"} <= data.keys() else empty
    )
    a, b, c = st.columns(3)
    derived_metric(
        a,
        "Nonfinancial equity value / GDP",
        market_gdp,
        "{:.0f}%",
        "Z.1 / BEA",
        None if market_gdp.empty else f"{ordinal(history_percentile(market_gdp))} percentile",
        inverse=True,
    )
    derived_metric(
        b,
        "After-tax profits / GDP",
        profits_gdp,
        "{:.1f}%",
        "BEA",
        None if profits_gdp.empty else f"{ordinal(history_percentile(profits_gdp))} percentile",
    )
    z = zscore(market_gdp) if not market_gdp.empty else np.nan
    c.metric("Equity value / GDP z-score", f"{z:+.2f}σ" if np.isfinite(z) else "—")
    c.caption("DERIVED · full retained sample")
    left, right = st.columns(2)
    with left:
        fig = line_figure(
            "DERIVED · Nonfinancial corporate equity value / GDP (%)",
            {"Equity value / GDP": clip(market_gdp, start)},
            left_title="Percent of GDP",
        )
        for name, level in bands(market_gdp).items():
            fig.add_hline(
                y=level,
                line_dash="dot" if name != "mean" else "dash",
                line_color="#94A3B8",
                annotation_text=name,
                annotation_position="right",
            )
        chart_or_note(
            ctx,
            fig,
            [{"m": market_gdp}],
            "valuation_mktgdp",
            "Requires Z.1 equities and GDP.",
            data,
            start,
        )
    with right:
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Corporate profits after tax / GDP (%)",
                {"Profits / GDP": clip(profits_gdp, start)},
                left_title="Percent of GDP",
            ),
            [{"p": profits_gdp}],
            "valuation_profits",
            "Requires CP and GDP.",
            data,
            start,
        )
    rates = {
        "10Y nominal": clip(data.get("DGS10", empty), start),
        "10Y real (TIPS)": clip(data.get("DFII10", empty), start),
        "10Y breakeven": clip(data.get("T10YIE", empty), start),
    }
    chart_or_note(
        ctx,
        line_figure(
            "Discount-rate backdrop: nominal, real and breakeven 10Y (%)",
            rates,
            left_title="Percent",
            zero=True,
        ),
        [rates],
        "valuation_rates",
        "Treasury/TIPS yields not ingested.",
        data,
        start,
    )


def _models(ctx, data):
    with st.expander("Justified P/E model and sensitivity (assumptions)", expanded=False):
        a, b, c = st.columns(3)
        cost = a.number_input("Assumed cost of equity (%)", value=9.0, key="jpe_cost") / 100
        growth = b.number_input("Assumed sustainable growth (%)", value=4.0, key="jpe_growth") / 100
        retention = c.slider("Assumed retention ratio", 0.0, 1.0, 0.5, key="jpe_retention")
        try:
            st.metric("DERIVED · justified P/E", f"{justified_pe(cost, growth, retention):.2f}×")
        except ValueError as exc:
            st.error(str(exc))
        costs = [round(cost * 100 + d, 2) for d in (-2, -1, -0.5, 0, 0.5, 1, 2)]
        growths = [round(growth * 100 + d, 2) for d in (-2, -1, 0, 1, 2)]
        grid = justified_pe_grid(costs, growths, retention)
        fig = px.imshow(
            grid.values,
            x=[f"r={r:.2f}%" for r in grid.columns],
            y=[f"g={g:.2f}%" for g in grid.index],
            text_auto=".1f",
            color_continuous_scale="Blues",
            aspect="auto",
            title="Justified P/E sensitivity · cost of equity × growth",
        )
        ctx.chart(fig, key="valuation_jpe_grid")
        st.caption(
            "P/E = (1 − retention) / (r − g). Blank cells: r ≤ g (undefined). Constant-growth "
            "assumptions; unstable near a zero denominator. Not an observed valuation."
        )
