"""FC Data: monthly share of each sector and style in the worst decile of the failure model.

Universe: top 1,000 US stocks, history from 1980 (Leveraged Borrowers from ~2010). Sponsor
research data updated manually each month. The workbook tab reproduces the sponsor's 14
charts; analytics add cross-sector comparison, a heatmap and recomputed statistics that are
checked against the sponsor's saved Failure Candidates summary.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.sections.common import (
    clip,
    line_figure,
    lookback_start,
    render_workbook,
    shade_recessions,
    workbook_series,
)
from dashboard.sections.extras import (
    tone_style,
    workbook_cells,
    workbook_sources,
    workbook_tabs,
    workbook_unavailable,
)
from dashboard.styles.theme import base_table_style
from src.analytics.empirical import history_stats

# Label -> (workbook series id, Failure Candidates summary row). Order follows FC Data rows 4-19.
SERIES = {
    "Energy": ("fc_data_0_0", 5),
    "Materials": ("fc_data_1_0", 6),
    "Industrials": ("fc_data_2_0", 7),
    "Consumer Discretionary": ("fc_data_3_0", 8),
    "Consumer Staples": ("fc_data_4_0", 9),
    "Health Care": ("fc_data_5_0", 10),
    "Financials": ("fc_data_6_0", 11),
    "Technology": ("fc_data_7_0", 12),
    "Communications": ("fc_data_8_0", 13),
    "Utilities": ("fc_data_9_0", 14),
    "Real Estate": ("fc_data_10_0", 15),
    "Big Growers": ("fc_data_11_0", 17),
    "Expensive": ("fc_data_12_0", 18),
    "Leveraged Borrowers": ("fc_data_13_0", 20),
}
STYLES = ("Big Growers", "Expensive", "Leveraged Borrowers")
RECESSION = "fc_data_0_1"
NOTES = [
    (
        "Share = fraction of each group's stocks (top 1,000 US stocks) that fall in the worst decile "
        "of the sponsor's failure model. 'Expensive' is the share of failure candidates with a "
        "forward P/E above 50x or losses. Sponsor research data, updated manually each month."
    ),
    (
        "Statistics are recomputed from the saved monthly history with the sponsor's definitions "
        "(FC Data!UV:VE): mean, sample standard deviation, (latest − mean) ÷ std, and changes over "
        "1/3/6/12 months. The 'Matches sponsor' column compares them with the saved Failure "
        "Candidates summary (tolerance 0.001)."
    ),
    "Recession bars come from the sponsor's own recession row (FC Data row 21).",
]


def load_all(title):
    return {label: workbook_series(title, sid) for label, (sid, _) in SERIES.items()}


def render(ctx, render_section):
    sponsor, analytics, data_tab, method = workbook_tabs()
    series = load_all(ctx.title)
    available = {k: v for k, v in series.items() if not v.empty}
    with sponsor:
        render_workbook(ctx.title, render_section)
    with analytics:
        if not workbook_unavailable(ctx.title) and available:
            recession = workbook_series(ctx.title, RECESSION)
            _compare(ctx, available, recession)
            _heatmap(ctx, available)
            _statistics(ctx, available)
    with data_tab:
        if available:
            frame = pd.DataFrame(available).sort_index()
            frame.index.name = "Month"
            st.caption("Fractions (0.12 = 12%). Blank = no saved observation.")
            ctx.table_view(
                frame.sort_index(ascending=False).reset_index().head(120), hide_index=True
            )
            st.download_button(
                "Export full history (CSV)", frame.to_csv(), "fc_data.csv", "text/csv"
            )
        else:
            st.info("UNAVAILABLE · No saved failure-candidate history.")
    with method:
        workbook_sources(ctx, ctx.title, NOTES)


def _compare(ctx, series, recession):
    st.subheader("Compare sectors and styles")
    options = list(series)
    default = [g for g in ("Technology", "Big Growers", "Expensive") if g in series]
    picked = st.multiselect("Groups", options, default=default or options[:1], key="fc_groups")
    start = lookback_start("fc_data", "20Y")
    lines = {label: clip(series[label] * 100, start) for label in picked}
    fig = line_figure(
        "Share in worst decile of the failure model (%)", lines, left_title="Percent of group"
    )
    shade_recessions(fig, {"USREC": recession}, start)
    if lines:
        ctx.chart(fig, key="fc_compare")
    else:
        st.info("Select at least one group.")


def _heatmap(ctx, series):
    st.subheader("Recent history across groups")
    months = st.segmented_control(
        "Months shown", [24, 36, 60], default=36, key="fc_heat_months", format_func=str
    )
    frame = pd.DataFrame(series).sort_index().tail(months or 36) * 100
    fig = go.Figure(
        go.Heatmap(
            z=frame.T.values,
            x=frame.index,
            y=frame.columns,
            colorscale=[[0, "#F0F8F2"], [0.5, "#FFF4DB"], [1, "#B91C1C"]],
            colorbar={"title": "%"},
            hovertemplate="%{y}<br>%{x|%b %Y}: %{z:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Share in worst decile (%)", height=520, yaxis={"autorange": "reversed"}
    )
    ctx.chart(fig, key="fc_heatmap")


def _statistics(ctx, series):
    st.subheader("Current reading versus history")
    cells = workbook_cells("Failure Candidates")
    rows = []
    for label, s in series.items():
        stats = history_stats(s)
        if stats is None:
            continue
        saved = SERIES[label][1]
        saved_mean, saved_z = cells.get(f"AE{saved}"), cells.get(f"AF{saved}")
        match = None
        if isinstance(saved_mean, (int, float)) and isinstance(saved_z, (int, float)):
            match = bool(
                abs(saved_mean - stats["mean"]) < 1e-3 and abs(saved_z - stats["from_mean"]) < 1e-3
            )
        rows.append(
            {
                "Group": label,
                "Type": "Style" if label in STYLES else "Sector",
                "Month": stats["as_of"],
                "Latest (%)": stats["latest"] * 100,
                "Mean (%)": stats["mean"] * 100,
                "Std. dev. from mean": stats["from_mean"],
                "Percentile": stats["percentile"],
                "1M (pp)": stats["chg_1m"] * 100,
                "3M (pp)": stats["chg_3m"] * 100,
                "12M (pp)": stats["chg_12m"] * 100,
                "Max (%)": stats["max"] * 100,
                "Matches sponsor": "—" if match is None else "Yes" if match else "No",
            }
        )
    frame = pd.DataFrame(rows)
    above = frame["Std. dev. from mean"] > 0
    bar = go.Figure(
        go.Bar(
            x=frame["Std. dev. from mean"],
            y=frame["Group"],
            orientation="h",
            marker_color=np.where(above, "#B91C1C", "#15803D"),
            hovertemplate="%{y}: %{x:+.2f} std. dev.<extra></extra>",
        )
    )
    bar.update_layout(
        title="Std. dev. from historical mean (red = more failure candidates than usual)",
        height=460,
        yaxis={"autorange": "reversed"},
    )
    ctx.chart(bar, key="fc_zscores")
    numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
    styled = (
        base_table_style(frame)
        .format({c: "{:,.2f}" for c in numeric}, na_rep="—")
        .format(
            {
                "Std. dev. from mean": "{:+.2f}",
                "1M (pp)": "{:+.2f}",
                "3M (pp)": "{:+.2f}",
                "12M (pp)": "{:+.2f}",
            },
            na_rep="—",
        )
        .map(
            tone_style(lambda v: v < 0, lambda v: v > 0),
            subset=["Std. dev. from mean", "1M (pp)", "3M (pp)", "12M (pp)"],
        )
        .map(tone_style(lambda v: v == "Yes", lambda v: v == "No"), subset=["Matches sponsor"])
    )
    ctx.table_view(styled, hide_index=True, alt="Failure-candidate statistics by group")
    mismatches = (frame["Matches sponsor"] == "No").sum()
    if mismatches:
        st.warning(
            f"{mismatches} group(s) differ from the sponsor's saved summary. The workbook "
            "statistics may reference a different date range; review FC Data!UV:VE."
        )
