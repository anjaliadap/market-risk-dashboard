"""S&P Relative: the S&P 500 priced in gold and in oil, versus 7-year moving averages.

Primary data are the sponsor's saved monthly ratios (gold block B:H, oil block J:P). Analytics
add distance from the 7-year average, historical percentiles, and the S&P 500 / gold / oil
levels implied by a return to the average. FRED supplies an independent S&P 500 ÷ WTI spot
cross-check; no free gold price history is connected.
"""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    chart_or_note,
    clip,
    line_figure,
    load,
    lookback_start,
    page_tabs,
    refresh_controls,
    render_workbook,
    snapshot_table,
    sources_table,
    workbook_series,
)
from dashboard.sections.extras import add_reference, workbook_unavailable
from src.analytics.empirical import deviation, reversion_levels
from src.analytics.signals import percentile_rank, ratio

IDS = ["SP500", "DCOILWTICO", "USREC"]
TABLE = [("SP500", "pct"), ("DCOILWTICO", "pct")]
PAIRS = {
    "Gold": {
        "ratio": "sandp_relative_0_0",
        "average": "sandp_relative_0_1",
        "asset": "sandp_relative_2_1",
        "unit": "USD per troy ounce",
    },
    "Oil": {
        "ratio": "sandp_relative_1_0",
        "average": "sandp_relative_1_1",
        "asset": "sandp_relative_2_2",
        "unit": "USD per barrel (WTI CL1)",
    },
}
INDEX = "sandp_relative_2_0"
NOTES = [
    (
        "Ratios are the sponsor's saved monthly S&P 500 price index ÷ gold (USD/oz) and ÷ WTI "
        "front-month futures (CL1, USD/bbl); the 7-year average is the sponsor's saved formula. The "
        "latest row may be mid-month."
    ),
    (
        "Implied levels: S&P 500 if the ratio returned to its 7-year average with gold/oil unchanged "
        "(average × asset price), and gold/oil if the S&P 500 were unchanged (S&P ÷ average). These "
        "are arithmetic reference points, not forecasts."
    ),
    (
        "Percentiles rank the latest ratio within its saved history since 1950. Ratios mix index "
        "points and USD; they are research ratios, not investable returns."
    ),
    (
        "Independent cross-check: FRED S&P 500 (about 10 years) ÷ WTI spot (DCOILWTICO). Spot and "
        "front-month futures differ, so the levels will not match exactly. FRED no longer "
        "redistributes LBMA gold prices, so gold has no independent series here."
    ),
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        if not workbook_unavailable(ctx.title):
            _summary(ctx)
            _deviation(ctx)
        _independent(ctx, data)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "sp_relative_indicators.csv")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def _pair(title, spec):
    return (
        workbook_series(title, spec["ratio"]),
        workbook_series(title, spec["average"]),
        workbook_series(title, spec["asset"]),
    )


def _summary(ctx):
    st.subheader("Where the ratios stand")
    index = workbook_series(ctx.title, INDEX)
    rows = []
    for name, spec in PAIRS.items():
        ratio_s, average, asset = _pair(ctx.title, spec)
        if ratio_s.empty:
            continue
        latest = float(ratio_s.iloc[-1])
        avg = float(average.iloc[-1]) if len(average) else np.nan
        levels = (
            reversion_levels(float(index.iloc[-1]), float(asset.iloc[-1]), avg)
            if len(index) and len(asset)
            else None
        )
        rows.append(
            {
                "Ratio": f"S&P 500 ÷ {name.lower()}",
                "Month": ratio_s.index[-1].date(),
                "Latest": latest,
                "7Yr average": avg,
                "vs 7Yr average (%)": (latest / avg - 1) * 100 if avg and avg > 0 else np.nan,
                "Percentile since 1950": percentile_rank(ratio_s),
                "Long-run median": float(ratio_s.median()),
                "S&P 500 implied at 7Yr avg": levels["implied_index"] if levels else np.nan,
                "S&P change (%)": levels["index_change"] if levels else np.nan,
                f"{name} implied at 7Yr avg": levels["implied_asset"] if levels else np.nan,
                f"{name} change (%)": levels["asset_change"] if levels else np.nan,
            }
        )
    if not rows:
        st.info("UNAVAILABLE · Saved ratio history missing.")
        return
    columns = st.columns(len(rows) * 2)
    for i, row in enumerate(rows):
        columns[2 * i].metric(row["Ratio"], f"{row['Latest']:.2f}x")
        columns[2 * i].caption(f"Workbook · {row['Month']}")
        columns[2 * i + 1].metric(
            "vs 7-year average",
            "—" if np.isnan(row["vs 7Yr average (%)"]) else f"{row['vs 7Yr average (%)']:+.1f}%",
            help="Latest ratio ÷ sponsor's saved 7-year moving average − 1",
        )
        columns[2 * i + 1].caption(f"{row['Percentile since 1950']:.0f}th percentile since 1950")
    for row in rows:
        ctx.table_view(pd.DataFrame([row]), hide_index=True)
    st.caption("Implied levels are arithmetic reference points (see Methodology), not forecasts.")


def _deviation(ctx):
    st.subheader("Distance from the 7-year average")
    start = lookback_start("sp_relative", "Max")
    lines = {}
    for name, spec in PAIRS.items():
        ratio_s, average, _ = _pair(ctx.title, spec)
        lines[f"S&P ÷ {name.lower()}"] = clip(deviation(ratio_s, average), start)
    fig = line_figure(
        "DERIVED · Ratio versus its 7-year moving average (%)",
        lines,
        left_title="Percent above (+) / below (−) average",
        zero=True,
    )
    if any(len(s.dropna()) for s in lines.values()):
        ctx.chart(fig, key="sp_relative_deviation")
    else:
        st.info("UNAVAILABLE · Ratios or 7-year averages missing.")
    left, right = st.columns(2)
    for column, (name, spec) in zip((left, right), PAIRS.items(), strict=True):
        ratio_s, _, _ = _pair(ctx.title, spec)
        with column:
            if ratio_s.empty:
                continue
            series = {f"S&P ÷ {name.lower()}": clip(ratio_s, start)}
            fig = line_figure(
                f"S&P 500 ÷ {name.lower()} with historical bands", series, left_title="Ratio (x)"
            )
            for q, label in ((0.1, "10th pct"), (0.5, "median"), (0.9, "90th pct")):
                add_reference(fig, float(ratio_s.quantile(q)), label, dash="dot")
            ctx.chart(fig, key=f"sp_relative_bands_{name.lower()}")


def _independent(ctx, data):
    st.subheader("Independent cross-check: S&P 500 ÷ WTI spot (FRED)")
    empty = pd.Series(dtype=float)
    fred_ratio = ratio(data.get("SP500", empty), data.get("DCOILWTICO", empty), 7)
    monthly = fred_ratio.resample("ME").last().dropna() if len(fred_ratio) else empty
    saved = workbook_series(ctx.title, PAIRS["Oil"]["ratio"])
    start = monthly.index[0] - pd.DateOffset(months=1) if len(monthly) else None
    left = {"FRED: S&P 500 ÷ WTI spot (month-end)": monthly}
    right = {"Workbook: S&P 500 ÷ WTI CL1": clip(saved, start)} if len(saved) else {}
    fig = line_figure(
        "S&P 500 ÷ WTI: independent spot vs sponsor futures-based ratio",
        {**left, **right},
        left_title="Ratio (x)",
    )
    chart_or_note(
        ctx,
        fig,
        [left, right],
        "sp_relative_fred",
        "FRED S&P 500 / WTI not ingested. Run `uv run python -m scripts.refresh_market`.",
        data,
        start,
    )
    st.caption(
        "Same axis because both are S&P index points per USD/bbl; spot vs front-month futures "
        "and month-end vs mid-month sampling explain small gaps. Series are never merged."
    )
