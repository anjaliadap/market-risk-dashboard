"""Render workbook pages that were added after the original dashboard merge."""

import json
from pathlib import Path
from zipfile import BadZipFile

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from openpyxl.utils.exceptions import InvalidFileException

from dashboard.excel_views import build_figure, table_columns, table_frame
from dashboard.styles.theme import financial_table, research_chart
from src.process_sync import configured_workbook_path
from src.providers.excel import ExcelWorkbookProvider

MAPPING_PATH = Path(__file__).resolve().parents[1] / "config/additional_workbook_pages.json"
MAPPING = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner="Reading the saved workbook…", max_entries=20)
def read_section(path, modified_ns, size, title):
    # File metadata invalidates the cache when a saved workbook changes.
    mapping = {**MAPPING, "sections": {title: MAPPING["sections"][title]}}
    return ExcelWorkbookProvider(path, mapping).read()["sections"][title]


def add_linear_fit(figure, trace):
    points = [(x, y) for x, y in zip(trace.x, trace.y, strict=True) if y is not None]
    if len({x for x, _ in points}) < 2:
        return
    x, y = np.asarray(points, dtype=float).T
    slope, intercept = np.polyfit(x, y, 1)
    residuals = y - (slope * x + intercept)
    total = np.square(y - y.mean()).sum()
    r_squared = 1 - np.square(residuals).sum() / total if total else 0
    endpoints = np.array([x.min(), x.max()])
    figure.add_trace(
        go.Scatter(
            x=endpoints,
            y=slope * endpoints + intercept,
            mode="lines",
            line={"color": trace.line.color, "dash": "dot"},
            name=f"Linear fit · R² {r_squared:.3f}",
            yaxis=trace.yaxis,
            meta=trace.meta,
        )
    )


def workbook_figure(chart):
    figure = build_figure(chart)
    for spec, trace in zip(chart["series"], figure.data, strict=True):
        if "Scatter" in spec["kind"]:
            trace.mode = "markers"
        if spec.get("trendline") == "linear":
            add_linear_fit(figure, trace)
        if spec.get("x_title"):
            figure.update_xaxes(title_text=spec["x_title"])
        if spec.get("date_type") == "year":
            figure.update_xaxes(type="category")
        if spec.get("y_title"):
            axis = "yaxis" + (trace.yaxis or "y")[1:]
            figure.layout[axis].title.text = spec["y_title"]
    return figure


def render_additional_workbook_page(title, theme):
    if title not in MAPPING["sections"]:
        return False
    configured = configured_workbook_path()
    if not configured:
        st.info("Set PROCESS_WORKBOOK_PATH or EXCEL_WORKBOOK_PATH to the saved sponsor workbook.")
        return True
    path = Path(configured).expanduser()
    try:
        stat = path.stat()
        section = read_section(str(path), stat.st_mtime_ns, stat.st_size, title)
    except (OSError, ValueError, BadZipFile, InvalidFileException) as exc:
        st.warning(f"The saved workbook section is unavailable. {exc}")
        return True

    st.caption("Source: sponsor’s saved Excel workbook · Bloomberg refresh time unknown")
    for note in section["notes"]:
        st.caption(note)
    for table in section["tables"]:
        st.subheader(table["title"])
        financial_table(
            table_frame(table, mapped_headers=True),
            theme,
            hide_index=True,
            width="stretch",
            alt=table["title"],
            column_config=table_columns(table),
        )
    for chart in section["charts"]:
        if any(
            point["value"] is not None for series in chart["series"] for point in series["points"]
        ):
            research_chart(workbook_figure(chart), theme, width="stretch", key=chart["id"])
        else:
            st.info(f"{chart['title']}: no valid saved observations.")
    return True
