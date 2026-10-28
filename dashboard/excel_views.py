"""Reusable sponsor-table and Plotly rendering; all cell mappings live outside the UI."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.styles.theme import (
    BACKGROUND,
    CONFIG,
    NEGATIVE,
    SURFACE,
    TEXT,
    base_table_style,
    financial_table,
    page_header,
    research_chart,
    series_color,
    signed_style,
    style_figure,
    theme_for,
)
from src.excel_sync import latest_import, poll_workbook, workbook_file_status
from src.providers.excel import load_mapping
from src.settings import settings


def format_cell(cell):
    value, fmt = cell["value"], cell["format"]
    if value is None:
        return ""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)
    if "%" in fmt:
        decimals = len(fmt.split("%", 1)[0].split(".")[-1]) if "." in fmt else 0
        return f"{value:.{min(decimals, 3)}%}"
    if '"x"' in fmt.lower() or '"×"' in fmt:
        return f"{value:,.2f}×"
    prefix = "$" if "$" in fmt else ""
    return prefix + f"{value:,.2f}".rstrip("0").rstrip(".")


def build_figure(chart):
    secondary = any(s["secondary"] for s in chart["series"])
    fig = make_subplots(specs=[[{"secondary_y": secondary}]])
    axis_formats = {False: [], True: []}
    markers = []
    for series in chart["series"]:
        points = series["points"]
        x = [p["date"] for p in points]
        y = [p["value"] for p in points]
        custom = [
            [p["cell"], "Forward estimate" if p["forward"] else "Saved history"] for p in points
        ]
        number = (
            "%{y:.1%}"
            if "%" in series["unit"]
            else "%{y:$,.2f}"
            if "$" in series["unit"]
            else "%{y:,.2f}"
        )
        common = {
            "x": x,
            "y": y,
            "name": series["name"],
            "customdata": custom,
            "hovertemplate": "%{x}<br>"
            + number
            + "<br>%{customdata[1]}<br>Source cell %{customdata[0]}<extra>%{fullData.name}</extra>",
        }
        color = series_color(series["name"])
        # Excel uses narrow full-height bars to mark the last reported quarter.
        # Render those as a proper vertical marker, leaving the financial series untouched.
        marker_series = series.get("role") == "reported_marker"
        if marker_series:
            valid = [p for p in points if p["value"] not in (None, 0)]
            if len(valid) <= 1 and series.get("latest_reported"):
                markers.append(series["latest_reported"])
                continue
        if "Bar" in series["kind"]:
            trace = go.Bar(**common, marker_color=color)
        else:
            trace = go.Scatter(
                **common, mode="lines", connectgaps=False, line={"color": color, "width": 1.6}
            )
        fig.add_trace(trace, secondary_y=series["secondary"] if secondary else None)
        axis_formats[series["secondary"]].append(series["unit"])
        if series.get("latest_reported"):
            markers.append(series["latest_reported"])
    for marker in sorted(set(markers)):
        fig.add_vline(x=marker, line_color=NEGATIVE, line_width=1.3)
    for right, formats in axis_formats.items():
        if not formats:
            continue
        args = {"tickformat": ".0%"} if all("%" in f for f in formats) else {}
        if secondary:
            fig.update_yaxes(secondary_y=right, **args)
        else:
            fig.update_yaxes(**args)
    fig.update_layout(
        title=chart["title"],
        height=390,
        template="plotly_white",
        barmode="relative",
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.22},
        margin={"l": 40, "r": 40, "t": 55, "b": 65},
    )
    return style_figure(fig)


def render_section(title):
    """Return whether the workbook owns this section, including unavailable caches."""
    if title == "Executive Overview":
        saved = latest_import(success_only=True)
        if not saved:
            return False
        snapshot = saved["snapshot"]
        st.caption(
            f"Primary source: sponsor saved workbook · latest historical date {snapshot['latest_observation']} · imported {saved['time']} UTC"
        )
        st.info(
            "Bloomberg refresh time is unknown. Workbook caches include both reported history and forward estimates."
        )
        financial_table(
            pd.DataFrame(
                [
                    {
                        "Section": name,
                        "Charts": len(section["charts"]),
                        "Tables": len(section["tables"]),
                    }
                    for name, section in snapshot["sections"].items()
                ]
            ),
            hide_index=True,
        )
        st.caption(
            "Source: validated Excel snapshot. Supply has no workbook source; Forecasting retains analyst assumptions. Review Workbook Administration for missing values and manual dependencies."
        )
        return True
    if title not in load_mapping()["sections"]:
        return False
    saved = latest_import(success_only=True)
    if not saved or title not in saved["snapshot"]["sections"]:
        if settings.excel_workbook_path:
            st.info(
                "Workbook is configured but no validated snapshot is available yet. Check Workbook Administration. Independent-source coverage follows below."
            )
        return False
    section = saved["snapshot"]["sections"][title]
    st.caption(
        f"Primary source: sponsor Excel workbook · imported {saved['time']} UTC · Bloomberg refresh time unknown"
    )
    st.caption(
        "Saved calculations and benchmarks are preserved. Forward estimates are distinguished from reported history."
    )
    for table in section["tables"]:
        st.subheader(table["title"])
        financial_table(
            table_frame(table),
            hide_index=True,
            width="stretch",
            alt=table["title"],
            column_config=table_columns(table),
        )
        st.caption(
            f"Source: saved workbook · {table['sheet']} · as of {table['as_of'] or 'not supplied (undated snapshot)'} · number formats retained"
        )
    columns = st.columns(2) if len(section["charts"]) > 1 else [st.container()]
    for i, chart in enumerate(section["charts"]):
        with columns[i % len(columns)]:
            valid = [
                p["date"]
                for s in chart["series"]
                for p in s["points"]
                if p["value"] is not None and not p["forward"]
            ]
            research_chart(
                build_figure(chart), theme_for(title), width="stretch", key="excel_" + chart["id"]
            )
            st.caption(
                f"Source: saved Excel / sponsor Bloomberg and manual inputs · latest valid history: {max(valid) if valid else 'unavailable'}"
            )
            if any(
                p["value"] is None
                for s in chart["series"]
                if s.get("role") != "reported_marker"
                for p in s["points"]
            ):
                st.warning(
                    "Some saved values are unavailable. Gaps are preserved; no interpolation or Python formula recalculation."
                )
    with st.expander("Workbook source and manual dependencies"):
        for note in section["notes"]:
            st.write(note)
        st.caption(
            "Fixed source ranges reproduce the sponsor's saved charts; review the central mapping after extending Excel histories."
        )
    return True


def table_frame(table):
    columns = table.get("display_columns")
    if not columns:
        return pd.DataFrame([[format_cell(c) for c in row] for row in table["rows"]])
    values, styles = [], []
    for row in table["rows"]:
        cells = {"".join(filter(str.isalpha, c["cell"])): c for c in row}
        visible = [cells.get(col, {"value": None, "format": "General"}) for col, _ in columns]
        if not any(c["value"] is not None for c in visible):
            continue
        signal = cells.get(table.get("signal_column"), {}).get("value") == 1
        output, row_styles = [], []
        label = str(visible[0]["value"] or "").lower()
        benchmark = label.strip() in {
            "average",
            "avg",
            "median",
            "total",
            "total possible",
            "# present",
            "% present",
            "current",
        } or label.startswith(("avg ", "median ", "total ", "current "))
        current_column = "D" if table.get("id") == "bear_checklist" else "F"
        for (col, _), cell in zip(columns, visible, strict=True):
            number = isinstance(cell["value"], (int, float)) and not isinstance(cell["value"], bool)
            text = format_cell(cell)
            heatmap = (
                table.get("id") == "market_snapshot"
                and col in {"E", "F", "G", "H", "I", "J", "K", "L", "M"}
                and number
            )
            if heatmap and cell["value"] > 0:
                text = "+" + text
            color = NEGATIVE if cell.get("font_color") in ("FFFF0000", "00FF0000") else TEXT
            background = (
                CONFIG["grayBackgroundColor"]
                if benchmark
                else BACKGROUND
                if len(values) % 2
                else SURFACE
            )
            style = f"color: {color}; background-color: {background}; text-align: {'right' if number else 'left'}"
            if heatmap:
                style += "; " + signed_style(cell["value"])
            if benchmark:
                style += "; font-weight: 700"
            if signal and col == current_column:
                text += " · Signal present"
                style += f"; color: {NEGATIVE}; font-weight: 700"
            output.append(text)
            row_styles.append(style)
        values.append(output)
        styles.append(row_styles)
    frame = pd.DataFrame(values, columns=[label for _, label in columns])
    return base_table_style(frame).apply(
        lambda _: pd.DataFrame(styles, columns=frame.columns), axis=None
    )


def table_columns(table):
    """String-formatted Excel cells need explicit native-grid alignment."""
    numeric_columns = set()
    for row in table["rows"]:
        for cell in row:
            if isinstance(cell["value"], (int, float)):
                numeric_columns.add("".join(filter(str.isalpha, cell["cell"])))
    return {
        label: st.column_config.TextColumn(
            label, alignment="right" if col in numeric_columns else "left"
        )
        for col, label in table.get("display_columns", [])
    }


@st.fragment(run_every="10s")
def synchronization_status():
    message = poll_workbook()
    latest = latest_import(success_only=True)
    current = latest["id"] if latest else None
    previous = st.session_state.get("excel_snapshot_id")
    st.session_state.excel_snapshot_id = current
    if current != previous:
        st.rerun()
    if settings.excel_workbook_path:
        st.caption("Workbook synchronization · " + message)


def render_administration():
    page_header("Workbook Administration")
    st.write(
        "Local saved workbook imports preserve the last valid snapshot. Bloomberg refresh time is not inferred from file saves."
    )
    st.write(
        "Workbook location:",
        settings.excel_workbook_path or "Not configured; set EXCEL_WORKBOOK_PATH in .env",
    )
    file_status = workbook_file_status()
    st.write(
        "Latest workbook modification time (UTC):", file_status["modified_at"] or "Unavailable"
    )
    if file_status["error"] and settings.excel_workbook_path:
        st.warning("Source file unavailable; last valid snapshot retained: " + file_status["error"])
    if st.button("Reimport Workbook", disabled=not bool(settings.excel_workbook_path)):
        st.info(poll_workbook(force=True))
    latest = latest_import()
    valid = latest_import(success_only=True)
    if latest:
        st.write("Latest import attempt:", latest["time"], latest["status"])
        if latest["error"]:
            st.error(latest["error"])
    if not valid:
        st.info(
            "No successful workbook import. Existing independent-source pages remain available."
        )
    else:
        snapshot = valid["snapshot"]
        st.write("Last successful import (UTC):", valid["time"])
        modified = snapshot["modified_at"]
        st.write(
            "Imported workbook modification time (UTC):",
            pd.to_datetime(modified, unit="s", utc=True).isoformat()
            if modified is not None
            else "Unknown",
        )
        st.write(
            "Latest validated historical date:", snapshot["latest_observation"] or "Unavailable"
        )
        st.write(
            "Imported numeric metrics (chart series and table cells):", snapshot["metric_count"]
        )
        st.write("Workbook SHA-256:", snapshot["sha256"])
        financial_table(
            pd.DataFrame(
                [
                    {"Validation check": key.replace("_", " ").capitalize(), "Count": value}
                    for key, value in snapshot["diagnostics"].items()
                ]
            ),
            alt="Workbook validation counts",
        )
        st.caption(snapshot["refresh_attestation"])
        if snapshot["issues"]:
            financial_table(pd.DataFrame(snapshot["issues"]), hide_index=True)
    rows = []
    for name, spec in load_mapping()["sections"].items():
        imported = valid["snapshot"]["sections"].get(name) if valid else None
        points = (
            [p for c in imported["charts"] for s in c["series"] for p in s["points"]]
            if imported
            else []
        )
        rows.append(
            {
                "Section": name,
                "Worksheets": ", ".join(spec["sheets"]),
                "Charts": len(spec["charts"]),
                "Valid saved chart points": sum(p["value"] is not None for p in points),
                "Missing chart points": sum(p["value"] is None for p in points),
                "Manual dependencies / limitations": " ".join(spec["notes"]),
            }
        )
    rows.append(
        {
            "Section": "Supply",
            "Worksheets": "No workbook source",
            "Manual dependencies / limitations": "Independent provider strategy in docs/excel_integration_map.md; no verified observations",
        }
    )
    financial_table(pd.DataFrame(rows), hide_index=True)
    st.caption(
        "Only local processing is enabled. OneDrive/SharePoint Graph authentication and redistribution permissions are not configured."
    )
