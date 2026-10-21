"""Shared UI tokens and renderers; financial data and calculations stay untouched."""

from dataclasses import dataclass
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

BACKGROUND = "#F5F7FA"
SURFACE = "#FFFFFF"
TEXT = "#263445"
MUTED = "#64748B"
BORDER = "#DFE5ED"
POSITIVE = "#39735E"
NEGATIVE = "#A65358"
AMBER = "#94641D"


@dataclass(frozen=True)
class Theme:
    category: str
    accent: str
    soft: str
    palette: tuple[str, ...]


THEMES = {
    "Market": Theme("Market", "#233E60", "#EBF0F6", ("#233E60", "#648AA4", "#6C8677", "#A68A62")),
    "Macro": Theme("Macro", "#28665E", "#EAF3EF", ("#28665E", "#67988D", "#526D86", "#AD956C")),
    "AI": Theme("AI", "#654567", "#F2EDF4", ("#654567", "#94809F", "#5C8A8A", "#B19A76")),
}


def theme_for(title, groups):
    category = next((name for name, titles in groups.items() if title in titles), "Market")
    return THEMES[category]


def apply_theme(theme):
    css = (Path(__file__).parent / "institutional.css").read_text()
    variables = f":root {{ --research-accent: {theme.accent}; --research-soft: {theme.soft}; }}"
    st.markdown(f"<style>{variables}\n{css}</style>", unsafe_allow_html=True)


def page_header(title, theme):
    apply_theme(theme)
    st.markdown(
        f'<div class="research-eyebrow">MARKET &amp; RISK INTELLIGENCE'
        f'<span class="research-category">{escape(theme.category)} research</span></div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption("Research workspace · Public-source observations · Delayed data")


def signed_style(value):
    if pd.isna(value) or value == 0:
        return ""
    color = POSITIVE if value > 0 else NEGATIVE
    background = "#EFF6F2" if value > 0 else "#FAF0F0"
    return f"color: {color}; background-color: {background}; font-weight: 600"


def status_style(value):
    text = str(value).lower()
    if any(word in text for word in ("failed", "error")):
        return f"color: {NEGATIVE}; background-color: #FAF0F0"
    if any(word in text for word in ("unavailable", "stale", "delayed", "pending")):
        return f"color: {AMBER}; background-color: #FCF5E8"
    if "success" in text or "available" in text:
        return f"color: {POSITIVE}; background-color: #EFF6F2"
    return ""


def financial_table(frame, theme, **kwargs):
    """Format the view only. CSV exports continue to use the original DataFrame."""
    # Put identifiers first in snapshots; retain the original frame for downloads.
    leading = [
        c
        for c in ("Series", "Latest", "Units", "Observation", "Status", "Change units")
        if c in frame
    ]
    frame = frame.loc[:, leading + [c for c in frame if c not in leading]]
    numeric = list(frame.select_dtypes(include="number").columns)
    signed_columns = [
        c
        for c in numeric
        if c in {"YTD", "1M", "3M", "6M", "12M", "free_cash_flow"}
        or str(c).startswith("Distance to")
        or c in {"from_high_pct", "from_low_pct"}
    ]
    styled = frame.style.format({c: "{:,.2f}" for c in numeric}, na_rep="—")
    integers = [c for c in numeric if c in {"year", "n", "new_versions"}]
    if integers:
        styled = styled.format({c: "{:,.0f}" for c in integers}, na_rep="—")
    if signed_columns:
        styled = styled.map(signed_style, subset=signed_columns)
    statuses = [c for c in frame if str(c).lower() in {"status", "quality"}]
    if statuses:
        styled = styled.map(status_style, subset=statuses)
    column_config = {
        c: st.column_config.LinkColumn(str(c), display_text="View source ↗")
        for c in frame
        if str(c).lower() in {"source", "url", "endpoint"}
        and not frame[c].dropna().empty
        and frame[c].dropna().astype(str).str.startswith(("https://", "http://")).all()
    }
    st.dataframe(
        styled,
        hide_index=kwargs.pop("hide_index", True),
        width=kwargs.pop("width", "stretch"),
        row_height=36,
        column_config=column_config,
        **kwargs,
    )


def research_chart(figure, theme, **kwargs):
    """Consistent figure styling without modifying observations or series names."""
    figure.update_layout(
        template="plotly_white",
        colorway=list(theme.palette),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "Arial, sans-serif", "size": 12, "color": TEXT},
        title={"font": {"size": 15, "color": theme.accent}, "x": 0.02, "xanchor": "left"},
        margin={"l": 28, "r": 24, "t": 68, "b": 48},
        height=380,
        hovermode="x unified",
        hoverlabel={"bgcolor": SURFACE, "font_color": TEXT, "bordercolor": BORDER},
        legend={"orientation": "h", "y": -0.22, "x": 0, "title_text": ""},
    )
    # Express assigns explicit trace colors; recolor each trace as well as the layout.
    for index, trace in enumerate(figure.data):
        if trace.type == "scatter":
            trace.update(
                line={"color": theme.palette[index % len(theme.palette)], "width": 2.2},
                marker={"color": theme.palette[index % len(theme.palette)], "size": 6},
            )
    figure.update_xaxes(showgrid=False, showline=True, linecolor=BORDER, zeroline=False)
    figure.update_yaxes(gridcolor="#EDF0F4", zerolinecolor=BORDER, tickformat=",~g")
    st.plotly_chart(
        figure,
        width=kwargs.pop("width", "stretch"),
        theme=None,
        config={"displaylogo": False, "scrollZoom": False, "toImageButtonOptions": {"scale": 2}},
        **kwargs,
    )
