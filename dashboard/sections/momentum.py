"""Momentum (workbook tab "Mo"): Momentum & Controversy Scores for large-cap stocks.

The score is the sponsor's monthly research series (top quintile of 9-month price trends,
percentile ranks, 100 = highest). The sponsor marks readings above 70 as crowded momentum
(e.g., Jan 2000 tech, Dec 2020); this page adds the signal board, episode history and what the
S&P 500 did after past threshold crossings.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.sections.common import clip, lookback_start, render_workbook, workbook_series
from dashboard.sections.extras import (
    add_reference,
    checklist,
    workbook_sources,
    workbook_tabs,
    workbook_unavailable,
)
from src.analytics.empirical import change_over, episodes, signal_study
from src.analytics.signals import Check, percentile_rank

SCORE, AVERAGE, THRESHOLD = "momentum_0_0", "momentum_0_1", "momentum_0_2"
SP500 = ("S&P Relative", "sandp_relative_2_0")  # sponsor's saved monthly S&P 500 level
DEFAULT_THRESHOLD = 70.0
NOTES = [
    (
        "Score: share-weighted percentile rank (100 = highest) of large-cap stocks in the top quintile "
        "of nine-month price trends, smoothed over three months. Sponsor research data, updated "
        "manually each month; there is no public equivalent."
    ),
    (
        "Threshold and average are the sponsor's saved rows (70 and the full-sample mean). Episodes "
        "are consecutive months at or above the threshold."
    ),
    (
        "Forward S&P 500 returns use the sponsor's saved monthly S&P 500 level (S&P Relative tab) and "
        "exclude dividends. Crossings are few and their windows overlap, so the study is descriptive "
        "and is not evidence of predictive power."
    ),
]


def render(ctx, render_section):
    sponsor, analytics, data_tab, method = workbook_tabs()
    score = workbook_series(ctx.title, SCORE)
    with sponsor:
        render_workbook(ctx.title, render_section)
    with analytics:
        if not workbook_unavailable(ctx.title) and not score.empty:
            threshold = _threshold(ctx.title)
            _signal_board(ctx, score, threshold)
            _history(ctx, score, threshold)
            _episodes_and_study(ctx, score, threshold)
    with data_tab:
        if not score.empty:
            frame = pd.DataFrame(
                {
                    "Score": score,
                    "Average": workbook_series(ctx.title, AVERAGE),
                    "Threshold": workbook_series(ctx.title, THRESHOLD),
                }
            )
            frame.index.name = "Month"
            ctx.table_view(frame.sort_index(ascending=False).reset_index(), hide_index=True)
            st.download_button(
                "Export history (CSV)", frame.to_csv(), "momentum_scores.csv", "text/csv"
            )
        else:
            st.info("UNAVAILABLE · No saved momentum history.")
    with method:
        workbook_sources(ctx, ctx.title, NOTES)


def _threshold(title):
    saved = workbook_series(title, THRESHOLD)
    return float(saved.iloc[-1]) if len(saved) else DEFAULT_THRESHOLD


def _signal_board(ctx, score, threshold):
    st.subheader("Momentum signal board")
    latest, as_of = float(score.iloc[-1]), score.index[-1].date()
    average = float(score.mean())
    rank = percentile_rank(score)
    change_3m = change_over(score, 3)
    checks = [
        Check(
            "Crowded momentum",
            f"≥ {threshold:.0f}",
            f"Score at or above the sponsor's {threshold:.0f} threshold",
            f"{latest:.1f}",
            "Above threshold" if latest >= threshold else "Below threshold",
            latest >= threshold,
            as_of,
            "Workbook (saved)",
        ),
        Check(
            "Historically extreme",
            "Top decile",
            "Score at or above the 90th percentile of its history since 1955",
            f"{rank:.0f}th percentile",
            "Top decile" if rank >= 90 else "Not top decile",
            rank >= 90,
            as_of,
            "Workbook (saved)",
        ),
        Check(
            "Building momentum",
            "Above average and rising",
            "Score above its long-run average and higher than three months earlier",
            f"{latest - average:+.1f} pts vs average; {change_3m:+.1f} pts over 3M",
            "Building" if latest > average and change_3m > 0 else "Not building",
            None if np.isnan(change_3m) else bool(latest > average and change_3m > 0),
            as_of,
            "Workbook (saved)",
        ),
    ]
    checklist(ctx, checks, "momentum_signal_board", "signals")
    cols = st.columns(4)
    cols[0].metric("Latest score", f"{latest:.1f}", f"{change_over(score, 1):+.1f} M/M")
    cols[1].metric("Distance to threshold", f"{latest - threshold:+.1f} pts")
    cols[2].metric("vs long-run average", f"{latest - average:+.1f} pts")
    change_12m = change_over(score, 12)
    cols[3].metric("12-month change", "—" if np.isnan(change_12m) else f"{change_12m:+.1f} pts")
    st.caption(f"Saved through {as_of}. Points are percentile-rank points, not percent returns.")


def _history(ctx, score, threshold):
    st.subheader("Score history and crowded-momentum episodes")
    start = lookback_start("momentum", "Max")
    shown = clip(score, start)
    fig = go.Figure(
        go.Scatter(
            x=shown.index, y=shown.values, name="Momentum & Controversy Scores", mode="lines"
        )
    )
    add_reference(fig, float(score.mean()), f"average {score.mean():.1f}", dash="dot")
    add_reference(fig, threshold, f"threshold {threshold:.0f}")
    runs = episodes(score, threshold)
    for run in runs:
        if start is not None and pd.Timestamp(run["end"]) < start:
            continue
        fig.add_vrect(
            x0=run["start"], x1=run["end"], fillcolor="#B45309", opacity=0.12, line_width=0
        )
    for run in sorted(runs, key=lambda r: r["peak"], reverse=True)[:3]:
        if start is None or pd.Timestamp(run["peak_date"]) >= start:
            fig.add_annotation(
                x=run["peak_date"],
                y=run["peak"],
                text=pd.Timestamp(run["peak_date"]).strftime("%b '%y"),
                showarrow=True,
                arrowhead=2,
                ay=-30,
            )
    fig.add_trace(
        go.Scatter(
            x=[shown.index[-1]],
            y=[shown.iloc[-1]],
            mode="markers+text",
            text=["Current"],
            textposition="top center",
            name="Current",
            marker={"size": 9},
        )
    )
    fig.update_layout(
        title="Large-cap stocks: top quintile of 9M price trend controversy scores",
        yaxis_title="Percentile rank (100 = highest)",
    )
    ctx.chart(fig, key="momentum_history")
    st.caption(
        "Shaded: months at or above the threshold. Labels mark the three highest episode peaks."
    )


def _episodes_and_study(ctx, score, threshold):
    st.subheader("Past episodes and S&P 500 afterwards")
    runs = episodes(score, threshold)
    if runs:
        table = pd.DataFrame(runs).rename(
            columns={
                "start": "Start",
                "end": "End",
                "months": "Months",
                "peak": "Peak score",
                "peak_date": "Peak month",
                "ongoing": "Ongoing",
            }
        )
        ctx.table_view(table.sort_values("Start", ascending=False), hide_index=True)
    else:
        st.info(f"No month at or above {threshold:.0f} in the saved history.")
    prices = workbook_series(*SP500)
    if prices.empty:
        st.info(
            "UNAVAILABLE · S&P 500 forward returns need the S&P Relative tab's saved monthly "
            "S&P 500 level in the same snapshot."
        )
        return
    events, summary = signal_study(score, prices, threshold)
    ctx.table_view(summary, hide_index=True)
    st.caption(
        f"Price returns after each upward crossing of {threshold:.0f} versus all months since "
        f"{max(score.index[0], prices.index[0]).year}. Descriptive only: few, overlapping events."
    )
    if len(events):
        with st.expander("Each crossing"):
            ctx.table_view(events.sort_values("Crossing", ascending=False), hide_index=True)
