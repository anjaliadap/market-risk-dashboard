"""Failure Candidates: latest share of failure candidates by sector & style, versus history,
combined with the OPP and Patient portfolios' sector weights.

The sponsor flags a position as 'Risk' when a portfolio is overweight a sector (versus S&P 500
weights) whose failure-candidate share is above its historical mean.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.sections.common import render_workbook, workbook_section
from dashboard.sections.extras import (
    tone_style,
    workbook_cells,
    workbook_sources,
    workbook_tabs,
    workbook_unavailable,
)
from dashboard.styles.theme import base_table_style
from src.analytics.empirical import overweight, position_risk

ROWS = range(5, 21)
COLUMNS = {
    "AC": "Sector",
    "AD": "Failure model",
    "AE": "Historical mean",
    "AF": "Std. dev. from mean",
    "AG": "1M",
    "AH": "3M",
    "AI": "6M",
    "AJ": "12M",
    "AK": "Weight: OPP",
    "AL": "Weight: Patient",
    "AM": "Weight: S&P",
    "AO": "Relative: OPP",
    "AP": "Relative: Patient",
    "AR": "Position: OPP",
    "AS": "Position: Patient",
}
PERCENT = [
    "Failure model",
    "Historical mean",
    "1M",
    "3M",
    "6M",
    "12M",
    "Weight: OPP",
    "Weight: Patient",
    "Weight: S&P",
]
PORTFOLIOS = {"OPP": "Weight: OPP", "Patient": "Weight: Patient"}
NOTES = [
    (
        "Failure model = latest share of the group's stocks in the worst decile of the sponsor's "
        "failure model; historical mean, std. dev. from mean and trailing changes come from FC Data."
    ),
    (
        "OPP and Patient weights are the sponsor's manual portfolio inputs; S&P weights are S&P 500 "
        "GICS sector weights from Bloomberg (S5xxxx Index)."
    ),
    (
        "Rules (sponsor formulas, re-applied here as a check): Overweight if portfolio weight > S&P "
        "weight; 'Risk' if Overweight and std. dev. from mean > 0, 'Less Risk' if Overweight and ≤ 0. "
        "Underweight sectors carry no position flag."
    ),
    (
        "Colors: green = fewer failure candidates than usual / falling, red = more than usual / "
        "rising. For relative weight, green = Overweight and red = Underweight, as in the sponsor "
        "sheet."
    ),
]


def table(title):
    """Saved summary as a frame (fractions kept as fractions); empty when unavailable."""
    cells = workbook_cells(title)
    rows = []
    for r in ROWS:
        label = cells.get(f"AC{r}")
        if not isinstance(label, str) or not label.strip():
            continue
        row = {}
        for col, name in COLUMNS.items():
            value = cells.get(f"{col}{r}")
            row[name] = value if value is not None else np.nan
        rows.append(row)
    return pd.DataFrame(rows, columns=list(COLUMNS.values()))


def render(ctx, render_section):
    sponsor, analytics, data_tab, method = workbook_tabs()
    frame = table(ctx.title)
    with sponsor:
        render_workbook(ctx.title, render_section)
    with analytics:
        if not workbook_unavailable(ctx.title) and len(frame):
            _as_of(ctx.title)
            _risk_board(ctx, frame)
            _matrix(ctx, frame)
            _positioning(ctx, frame)
    with data_tab:
        if len(frame):
            ctx.table_view(frame, hide_index=True)
            st.download_button(
                "Export summary (CSV)",
                frame.to_csv(index=False),
                "failure_candidates.csv",
                "text/csv",
            )
        else:
            st.info("UNAVAILABLE · No saved failure-candidate summary.")
    with method:
        workbook_sources(ctx, ctx.title, NOTES)


def _as_of(title):
    section = workbook_section(title)
    as_of = section["tables"][0].get("as_of") if section and section["tables"] else None
    st.caption(f"Latest failure-model month: {as_of or 'not supplied'}. Weights are manual inputs.")


def recompute(frame):
    """Re-apply the sponsor's relative-weight and risk rules to the saved inputs."""
    out = frame.copy()
    for name, column in PORTFOLIOS.items():
        weights = pd.to_numeric(out[column], errors="coerce")
        benchmark = pd.to_numeric(out["Weight: S&P"], errors="coerce")
        relative = [
            overweight(w, b) if pd.notna(w) and pd.notna(b) else None
            for w, b in zip(weights, benchmark, strict=True)
        ]
        out[f"Rule relative: {name}"] = relative
        out[f"Rule position: {name}"] = [
            position_risk(r, z) for r, z in zip(relative, out["Std. dev. from mean"], strict=True)
        ]
    return out


def _risk_board(ctx, frame):
    st.subheader("Portfolio exposure to failure risk")
    checked = recompute(frame)
    sectors = checked[pd.to_numeric(checked["Weight: S&P"], errors="coerce").notna()]
    columns = st.columns(4)
    for i, (name, column) in enumerate(PORTFOLIOS.items()):
        risk = sectors[sectors[f"Rule position: {name}"] == "Risk"]
        overweight_count = (sectors[f"Rule relative: {name}"] == "Overweight").sum()
        weight = pd.to_numeric(risk[column], errors="coerce").sum()
        columns[2 * i].metric(f"{name}: sectors at 'Risk'", f"{len(risk)} of {overweight_count}")
        columns[2 * i].caption("Overweight sectors with above-average failure share")
        columns[2 * i + 1].metric(f"{name}: weight in 'Risk' sectors", f"{weight:.0%}")
        columns[2 * i + 1].caption(", ".join(risk["Sector"]) or "None")
    mismatches = []
    for name in PORTFOLIOS:
        for _, row in sectors.iterrows():
            for kind in ("Relative", "Position"):
                saved = row[f"{kind}: {name}"]
                rule = row[f"Rule {kind.lower()}: {name}"]
                saved = None if isinstance(saved, float) and np.isnan(saved) else saved
                if saved != rule:
                    mismatches.append(
                        f"{row['Sector']} {kind.lower()} ({name}): saved {saved}, rule {rule}"
                    )
    if mismatches:
        st.warning("Saved flags differ from the sponsor's rule: " + "; ".join(mismatches))
    else:
        st.caption(
            "Saved Overweight/Risk flags match the sponsor's rules re-applied to the inputs."
        )


def _matrix(ctx, frame):
    st.subheader("Failure candidates by sector & style")
    shown = frame.copy()
    for column in PERCENT:
        shown[column] = pd.to_numeric(shown[column], errors="coerce") * 100
    changes = ["Std. dev. from mean", "1M", "3M", "6M", "12M"]
    styled = (
        base_table_style(shown)
        .format({c: "{:.1f}%" for c in PERCENT}, na_rep="")
        .format({c: "{:+.1f}" for c in ["1M", "3M", "6M", "12M"]}, na_rep="")
        .format({"Std. dev. from mean": "{:+.2f}"}, na_rep="")
        .map(tone_style(lambda v: v < 0, lambda v: v > 0), subset=changes)
        .map(
            tone_style(lambda v: v == "Overweight", lambda v: v == "Underweight"),
            subset=["Relative: OPP", "Relative: Patient"],
        )
        .map(
            tone_style(lambda v: v == "Less Risk", lambda v: v == "Risk"),
            subset=["Position: OPP", "Position: Patient"],
        )
    )
    ctx.table_view(styled, hide_index=True, alt="Failure candidates by sector and style")
    st.caption("Shares and weights in percent; trailing changes in percentage points.")


def _positioning(ctx, frame):
    st.subheader("Positioning versus failure risk")
    name = st.segmented_control("Portfolio", list(PORTFOLIOS), default="OPP", key="fc_portfolio")
    column = PORTFOLIOS[name or "OPP"]
    sectors = frame[pd.to_numeric(frame["Weight: S&P"], errors="coerce").notna()].copy()
    active = (
        pd.to_numeric(sectors[column], errors="coerce")
        - pd.to_numeric(sectors["Weight: S&P"], errors="coerce")
    ) * 100
    z = pd.to_numeric(sectors["Std. dev. from mean"], errors="coerce")
    risk = (active > 0) & (z > 0)
    left, right = st.columns(2)
    with left:
        fig = go.Figure(
            go.Scatter(
                x=active,
                y=z,
                mode="markers+text",
                text=sectors["Sector"],
                textposition="top center",
                marker={"size": 11, "color": np.where(risk, "#B91C1C", "#475569")},
                hovertemplate="%{text}<br>Active weight %{x:+.1f} pp<br>%{y:+.2f} std. dev."
                "<extra></extra>",
            )
        )
        fig.add_hline(y=0, line_width=1, line_color="#94A3B8")
        fig.add_vline(x=0, line_width=1, line_color="#94A3B8")
        fig.update_layout(
            title=f"{name or 'OPP'}: active weight vs failure-share z-score (red = 'Risk')",
            xaxis_title="Portfolio − S&P weight (pp)",
            yaxis_title="Std. dev. from historical mean",
            height=460,
        )
        ctx.chart(fig, key="fc_positioning")
    with right:
        bars = go.Figure(
            [
                go.Bar(
                    y=frame["Sector"],
                    x=pd.to_numeric(frame["Failure model"], errors="coerce") * 100,
                    name="Latest",
                    orientation="h",
                ),
                go.Bar(
                    y=frame["Sector"],
                    x=pd.to_numeric(frame["Historical mean"], errors="coerce") * 100,
                    name="Historical mean",
                    orientation="h",
                ),
            ]
        )
        bars.update_layout(
            title="Failure-candidate share: latest vs historical mean (%)",
            barmode="group",
            height=460,
            yaxis={"autorange": "reversed"},
        )
        ctx.chart(bars, key="fc_latest_vs_mean")
    st.caption("Top-right quadrant: overweight sectors with more failure candidates than usual.")
