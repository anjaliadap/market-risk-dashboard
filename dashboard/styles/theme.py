"""Light research design system. Tokens come from Streamlit's native theme contract."""

import json
import tomllib
from dataclasses import dataclass
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler

from src import provenance

CONFIG = tomllib.loads(
    (Path(__file__).resolve().parents[2] / ".streamlit/config.toml").read_text(encoding="utf-8")
)["theme"]
BACKGROUND = CONFIG["backgroundColor"]
SURFACE = CONFIG["secondaryBackgroundColor"]
TEXT = CONFIG["textColor"]
MUTED = CONFIG["grayTextColor"]
BORDER = CONFIG["borderColor"]
POSITIVE = CONFIG["greenTextColor"]
NEGATIVE = CONFIG["redTextColor"]
AMBER = CONFIG["yellowTextColor"]
POSITIVE_BG = CONFIG["greenBackgroundColor"]
NEGATIVE_BG = CONFIG["redBackgroundColor"]
WARNING_BG = CONFIG["yellowBackgroundColor"]
PALETTE = tuple(CONFIG["chartCategoricalColors"])


@dataclass(frozen=True)
class Theme:
    category: str
    accent: str
    soft: str
    palette: tuple[str, ...] = PALETTE


THEMES = {
    "Empirical": Theme("Empirical", CONFIG["orangeTextColor"], CONFIG["orangeBackgroundColor"]),
    "Market": Theme("Market", CONFIG["primaryColor"], "#F4EBF1"),
    "Macro": Theme("Macro", CONFIG["blueTextColor"], CONFIG["blueBackgroundColor"]),
    "AI": Theme("AI", CONFIG["violetTextColor"], CONFIG["violetBackgroundColor"]),
    "Operations": Theme(
        "Operations", CONFIG["sidebar"]["backgroundColor"], CONFIG["grayBackgroundColor"]
    ),
}


def theme_for(title, groups=None):
    if groups is None:
        groups = json.loads((Path(__file__).resolve().parents[2] / "config/pages.json").read_text())
    category = next((name for name, titles in groups.items() if title in titles), "Market")
    if title in {"Workbook Administration", "Data Sources & System Status"}:
        category = "Operations"
    return THEMES[category]


def apply_theme(theme):
    # Only our own markup and narrowly scoped native component surfaces need CSS.
    css = (Path(__file__).parent / "institutional.css").read_text()
    variables = f":root {{ --research-accent: {theme.accent}; --research-soft: {theme.soft}; --research-text: {TEXT}; --research-muted: {MUTED}; --research-surface: {SURFACE}; --research-border: {BORDER}; }}"
    st.html(f"<style>{variables}{css}</style>")


def page_header(title, theme=None):
    theme = theme or theme_for(title)
    apply_theme(theme)
    st.markdown(
        f'<div class="research-eyebrow">MARKET &amp; RISK INTELLIGENCE '
        f'<span class="research-category">{escape(theme.category)} research</span></div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption("Research workspace | Saved workbook and independent sources | Delayed data")


def signed_style(value):
    if pd.isna(value):
        return ""
    foreground, background = (
        (POSITIVE, POSITIVE_BG)
        if value > 0
        else (NEGATIVE, NEGATIVE_BG)
        if value < 0
        else (AMBER, WARNING_BG)
    )
    return f"color: {foreground}; background-color: {background}; font-weight: 600"


def status_style(value):
    text = str(value).lower()
    if any(word in text for word in ("failed", "error")):
        return f"color: {NEGATIVE}; background-color: {NEGATIVE_BG}"
    if any(word in text for word in ("unavailable", "stale", "delayed", "pending")):
        return f"color: {AMBER}; background-color: {WARNING_BG}"
    if "success" in text or "available" in text:
        return f"color: {POSITIVE}; background-color: {POSITIVE_BG}"
    return ""


def base_table_style(frame):
    styled = frame if isinstance(frame, Styler) else frame.style
    styled = styled.set_properties(**{"color": TEXT, "background-color": SURFACE})
    # Apply base styles first; semantic cell styles supplied later take precedence.
    styled = (
        styled.apply(
            lambda row: [f"background-color: {BACKGROUND if row.name % 2 else SURFACE}"] * len(row),
            axis=1,
        )
        if isinstance(styled.data.index, pd.RangeIndex)
        else styled
    )
    return styled.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", CONFIG["dataframeHeaderBackgroundColor"]),
                    ("color", CONFIG["dataframeHeaderTextColor"]),
                ],
            },
            {"selector": "td", "props": [("font-variant-numeric", "tabular-nums")]},
        ]
    )


def financial_table(frame, theme=None, **kwargs):
    """Native grid header colors come from config; signed styles retain numeric signs."""
    if isinstance(frame, Styler):
        styled = frame
        data = frame.data
    else:
        data = frame
        numeric = list(data.select_dtypes(include="number").columns)
        signed = [
            c
            for c in numeric
            if c
            in {"YTD", "1M", "3M", "6M", "12M", "free_cash_flow", "from_high_pct", "from_low_pct"}
            or str(c).startswith("Distance to")
        ]
        styled = base_table_style(data).format({c: "{:,.2f}" for c in numeric}, na_rep="—")
        integers = [
            c
            for c in numeric
            if c in {"year", "n", "new_versions", "Charts", "Tables"} or "points" in str(c).lower()
        ]
        if integers:
            styled = styled.format({c: "{:,.0f}" for c in integers}, na_rep="—")
        if signed:
            styled = styled.format({c: "{:+,.2f}" for c in signed}, na_rep="—").map(
                signed_style, subset=signed
            )
        statuses = [c for c in data if str(c).lower() in {"status", "quality"}]
        if statuses:
            styled = styled.map(status_style, subset=statuses)
    column_config = {
        c: st.column_config.LinkColumn(str(c), display_text="View source")
        for c in data
        if str(c).lower() in {"source", "url", "endpoint"}
        and not data[c].dropna().empty
        and data[c].dropna().astype(str).str.startswith(("https://", "http://")).all()
    }
    column_config.update(kwargs.pop("column_config", {}))
    st.dataframe(
        styled,
        hide_index=kwargs.pop("hide_index", True),
        width=kwargs.pop("width", "stretch"),
        # Every row visible: the table grows with its content instead of scrolling inside.
        height=kwargs.pop("height", "content"),
        row_height=36,
        column_config=centered(data, column_config),
        alt=kwargs.pop("alt", "Financial research table with source metadata"),
        **kwargs,
    )


def centered(data, column_config):
    """Center every column, keeping any other per-column settings (links, labels, formats)."""
    out = {}
    for column in data.columns:
        config = column_config.get(column, column_config.get(str(column)))
        if config is None:
            config = st.column_config.Column()
        elif isinstance(config, str):
            config = st.column_config.Column(config)
        out[column] = {**config, "alignment": "center"}
    for column, config in column_config.items():
        out.setdefault(column, config)
    return out


# Recurring series keep one color on every page. Everything else is colored in drawing order
# (plum, teal, slate, ...) like the PCM - Monthly Market & Risk Monitor workbook's own charts.
KNOWN_SERIES = {
    "revenue": 0,
    "capex + r&d": 1,
    "capex": 1,
    "aws": 2,
    "cloud": 2,
    "operating cash flow": 2,
    "free cash flow": 3,
    "combined": 4,
    "amzn": 0,
    "googl": 1,
    "meta": 2,
    "h100": 0,
    "b200": 1,
    "s&p 500 p/e": 0,
    "operating margin": 1,
    "roe": 1,
    "avg": 1,
    "lt avg.": 1,
    "ratio": 0,
}


def known_color(name):
    index = KNOWN_SERIES.get(str(name).strip().lower().replace("_", " "))
    return None if index is None else PALETTE[index]


def series_color(name):
    """Fixed color for a recurring series; the lead workbook color otherwise."""
    return known_color(name) or PALETTE[0]


def figure_colors(names):
    """One distinct palette color per trace: known identities first, then drawing order."""
    colors, used = [], set()
    for name in names:
        color = known_color(name)
        colors.append(color if color and color not in used else None)
        used.add(color)
    free = iter([c for c in PALETTE if c not in used] * 4)
    return [color or next(free, PALETTE[0]) for color in colors]


def style_figure(figure, theme=None):
    """Explicit foregrounds avoid Streamlit/Plotly theme mixing. Keep existing axis units."""
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "Arial, sans-serif", "size": 13, "color": TEXT},
        title={
            "font": {"size": 16, "color": TEXT},
            "x": 0.02,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
            "automargin": False,
        },
        hoverlabel={"bgcolor": SURFACE, "font": {"color": TEXT, "size": 13}, "bordercolor": BORDER},
        legend={
            "font": {"color": TEXT, "size": 12},
            "title_font": {"color": TEXT},
            "bgcolor": SURFACE,
            "orientation": "h",
            "y": -0.22,
            "x": 0,
        },
        colorway=list(PALETTE),
        margin={"l": 50, "r": 50, "t": 70, "b": 95},
        height=420,
        hovermode="x unified",
    )
    colored = [t for t in figure.data if t.type in ("scatter", "bar")]
    colors = dict(zip(map(id, colored), figure_colors([t.name for t in colored]), strict=True))
    dashes = ["solid", "dash", "dot"]
    for index, trace in enumerate(colored):
        color = colors[id(trace)]
        if trace.type == "scatter":
            trace.update(
                # Solid lines; dashes only once the palette has been used up.
                line={"color": color, "width": 2.4, "dash": dashes[index // len(PALETTE) % 3]},
                marker={"color": color},
                hoverlabel={"bgcolor": SURFACE, "font_color": TEXT},
            )
        elif trace.type == "bar":
            trace.update(
                marker={"color": color, "line": {"color": color, "width": 1}},
                hoverlabel={"bgcolor": SURFACE, "font_color": TEXT},
            )
    figure.update_xaxes(
        color=TEXT,
        tickfont={"color": TEXT},
        title_font={"color": TEXT},
        showgrid=False,
        showline=True,
        linecolor=BORDER,
        zeroline=False,
        automargin=True,
    )
    figure.update_yaxes(
        color=TEXT,
        tickfont={"color": TEXT},
        title_font={"color": TEXT},
        gridcolor=BORDER,
        zerolinecolor=BORDER,
        automargin=True,
    )
    for shape in figure.layout.shapes or []:
        if shape.type == "line":
            shape.line.color = NEGATIVE
    return figure


def chart_source_text(figure):
    """'Source: …' for a chart, built from the sources carried by its traces.

    Lines without a recorded source are derived inside the dashboard (for example a ratio or a
    moving average); they are attributed to the inputs this page read, never to a guessed provider.
    """
    traces = list(figure.data)
    if not traces:
        return None
    labelled = [provenance.sources_of(t) for t in traces]
    known = provenance.merge(*labelled)
    unlabelled = sum(not group for group in labelled)
    page = provenance.describe(provenance.page_sources())
    if known and not unlabelled:
        return "Source: " + provenance.describe(known)
    if known:
        tail = f"; other lines calculated from this page's inputs ({page})" if page else ""
        return "Source: " + provenance.describe(known) + tail
    if page:
        return "Source: calculated from this page's inputs: " + page
    return None


def research_chart(figure, theme=None, **kwargs):
    caption = kwargs.pop("source", None) or chart_source_text(figure)
    st.plotly_chart(
        style_figure(figure, theme),
        width=kwargs.pop("width", "stretch"),
        theme=None,
        alt=kwargs.pop("alt", figure.layout.title.text or "Financial research chart"),
        config={
            "displaylogo": False,
            "scrollZoom": False,
            "responsive": True,
            "toImageButtonOptions": {"scale": 2},
        },
        **kwargs,
    )
    if caption:
        st.caption(caption)
