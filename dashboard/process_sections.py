"""Pages for the sponsor's saved Gold, NDR and Empirical workbook inputs."""

import math
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles.numbers import is_date_format
from plotly.subplots import make_subplots

from dashboard.styles.theme import base_table_style, financial_table, research_chart, style_figure
from src.excel_sync import latest_import, workbook_file_status
from src.process_sync import poll_workbook
from src.settings import settings

PAGE_TITLES = ("Gold to Oil", "NDR", "Intra-Sector Spread", "Trend Following")
SOURCE_SHEETS = {
    "Gold to Oil": "Gold to Oil",
    "NDR": "NDR",
    "Intra-Sector Spread": "Intra-Sector Spreads",
    "Trend Following": "Trend-Following",
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _display(value, fmt):
    return format(value, fmt) if _number(value) else "Unavailable"


def _date(value):
    return str(value)[:10] if value else "not supplied"


def _notes(section):
    for note in section.get("notes", []):
        st.caption(str(note))


def _calculator_value(value, number_format):
    """Display supplied calculator values without evaluating spreadsheet formulas."""
    if value is None:
        return "Unavailable"
    if is_date_format(number_format):
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        # The provider normalizes dates using the source workbook's date epoch.
        return _date(value) if isinstance(value, str) else "Unavailable"
    if not _number(value):
        return "Unavailable"
    match = re.search(r"\.([0#]+)", number_format.split(";", 1)[0])
    precision = min(len(match.group(1)), 4) if match else 0
    amount = Decimal(str(value)) * (100 if "%" in number_format else 1)
    rounded = amount.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    if "%" in number_format:
        return format(rounded, f".{precision}f") + "%"
    prefix = "$" if "$" in number_format else ""
    if number_format == "General":
        return format(value, ",.2f").rstrip("0").rstrip(".")
    return prefix + format(rounded, f",.{precision}f")


def _render_ndr_calculator(calculator):
    with st.expander("Record-highs calculation"):
        if calculator.get("rows"):
            financial_table(
                pd.DataFrame(
                    [
                        {
                            "Measure": row["label"],
                            "Value": _calculator_value(
                                row.get("value"), row.get("format", "General")
                            ),
                        }
                        for row in calculator["rows"]
                    ]
                ),
                alt="Workbook record-highs scenario calculation with source labels",
            )
        else:
            st.info("The record-highs calculation is unavailable in the saved workbook.")
        st.caption(
            "Scenario reference date: "
            + _date(calculator.get("reference_date"))
            + " · target date: "
            + _date(calculator.get("target_date"))
            + "."
        )
        for note in calculator.get("notes", []):
            st.caption(str(note))


def build_gold_figure(section):
    """Keep the ratio and its source average separate from Brent's dollar axis."""
    history = sorted(section.get("history", []), key=lambda row: row["date"])
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    dates = [row["date"] for row in history]
    for field, name, secondary in (
        ("ratio", "Gold / Brent futures", False),
        ("average", "LT average", False),
        ("oil", "Brent futures (CO1)", True),
    ):
        figure.add_trace(
            go.Scatter(
                x=dates,
                y=[row.get(field) for row in history],
                name=name,
                mode="lines",
                connectgaps=False,
                hovertemplate=(
                    "%{x}<br>%{y:$,.2f}<extra>%{fullData.name}</extra>"
                    if secondary
                    else "%{x}<br>%{y:,.2f}×<extra>%{fullData.name}</extra>"
                ),
            ),
            secondary_y=secondary,
        )
    figure.update_layout(title="Gold to Brent futures")
    figure.update_yaxes(title_text="Gold / Brent (×)", ticksuffix="×", secondary_y=False)
    figure.update_yaxes(title_text="Brent futures (USD / barrel)", tickprefix="$", secondary_y=True)
    return figure


def _render_gold(section):
    current = section.get("current", {})
    columns = st.columns(3)
    for column, label, value, fmt in (
        (columns[0], "Gold / Brent futures", current.get("ratio"), ",.2f"),
        (columns[1], "Long-term average ratio", current.get("average"), ",.2f"),
        (columns[2], "Brent futures (CO1)", current.get("oil"), ",.2f"),
    ):
        shown = _display(value, fmt)
        if shown != "Unavailable":
            shown = "$" + shown if "CO1" in label else shown + "×"
        column.metric(label, shown)
    st.caption(
        f"Saved workbook reference date: {_date(current.get('date'))}. "
        "The date does not verify the timestamp of the Bloomberg quotes."
    )
    if section.get("history"):
        research_chart(build_gold_figure(section), key="process_gold_history")
    else:
        st.info("Gold and Brent history is unavailable in the saved workbook.")
    st.subheader("Prices implied by the long-term average")
    panels = st.columns(2)
    implied = section.get("implied", [])
    for panel, asset in zip(panels, ("Gold", "Brent futures"), strict=True):
        row = next((row for row in implied if row.get("asset") == asset), {})
        with panel:
            st.markdown("**" + asset + "**")
            frame = pd.DataFrame(
                [
                    {
                        "Measure": "Saved current price",
                        "Value": _display(row.get("current"), ",.2f"),
                    },
                    {
                        "Measure": "Implied price at LT average",
                        "Value": _display(row.get("implied"), ",.2f"),
                    },
                    {
                        "Measure": "Change to implied price",
                        "Value": _display(row.get("change"), "+.1%"),
                    },
                ]
            )
            # Currency is a display prefix rather than part of Python's numeric format.
            for index in (0, 1):
                value = row.get("current" if index == 0 else "implied")
                frame.loc[index, "Value"] = (
                    "$" + format(value, ",.2f") if _number(value) else "Unavailable"
                )
            financial_table(frame, alt=asset + " implied price comparison")
    st.caption(
        "Gold is USD per troy ounce; Brent (CO1) is the front-month futures price in USD per barrel. "
        "Implied prices use the workbook's long-term average ratio; they are arithmetic comparisons."
    )
    _notes(section)


def build_spread_figure(section):
    rows = section.get("current", [])
    figure = go.Figure()
    sectors = [row["sector"] for row in rows]
    figure.add_trace(
        go.Bar(
            y=sectors,
            x=[row.get("percentile") for row in rows],
            name="Current reading",
            orientation="h",
            hovertemplate="%{y}<br>Percentile %{x:.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            y=sectors,
            x=[row.get("average") for row in rows],
            name="LT average",
            mode="lines",
            hovertemplate="%{y}<br>Average percentile %{x:.0f}<extra></extra>",
        )
    )
    figure.update_layout(title="Intra-sector valuation spreads", hovermode="closest")
    figure.update_xaxes(title_text="Historical percentile", range=[0, 100], dtick=20)
    figure.update_yaxes(autorange="reversed")
    return figure


def _render_spread(section):
    st.caption(
        f"Current readings as of {_date(section.get('as_of'))}. Supplied percentile ranking window begins in 1952. "
        "Percentiles: 1 = narrowest spread; 100 = widest spread."
    )
    if not section.get("current"):
        st.info("Intra-sector percentile readings are unavailable in the saved workbook.")
        return
    figure = style_figure(build_spread_figure(section))
    figure.update_layout(
        height=max(440, 30 * len(section["current"]) + 120),
        hovermode="closest",
        margin={"l": 230, "r": 30, "t": 70, "b": 85},
    )
    st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key="process_spread_current",
        alt="Current intra-sector valuation percentiles compared with their long-term average",
        config={"displaylogo": False, "scrollZoom": False, "toImageButtonOptions": {"scale": 2}},
    )
    st.subheader("Current percentiles and changes")
    frame = pd.DataFrame(
        [
            {
                "Sector": row["sector"],
                "Percentile": row.get("percentile"),
                "LT average": row.get("average"),
                "1M change": row.get("change_1m"),
                "3M change": row.get("change_3m"),
                "6M change": row.get("change_6m"),
                "12M change": row.get("change_12m"),
            }
            for row in section["current"]
        ]
    )
    changes = [name for name in frame if name.endswith("change")]
    financial_table(
        base_table_style(frame).format(
            {"Percentile": "{:,.0f}", "LT average": "{:,.0f}", **{c: "{:+,.0f}" for c in changes}},
            na_rep="Unavailable",
        ),
        alt="Intra-sector percentiles and changes in percentile points",
    )
    st.caption(
        "Changes are in percentile points. Monthly readings are entered by the workbook owner."
    )
    _notes(section)


def build_trend_figure(section):
    history = sorted(section.get("history", []), key=lambda row: row["date"])
    figure = go.Figure(
        go.Scatter(
            x=[row["date"] for row in history],
            y=[row.get("quintile") for row in history],
            name="Trend Following Indicator 2.0",
            mode="lines",
            line_shape="hv",
            fill="tozeroy",
            connectgaps=False,
            hovertemplate="%{x}<br>Quintile %{y:.0f}<extra></extra>",
        )
    )
    figure.update_layout(title="Large-cap stocks — Trend Following Indicator 2.0", showlegend=False)
    figure.update_yaxes(title_text="Quintile", range=[0, 5.25], dtick=1)
    return figure


def _render_trend(section):
    current = section.get("current", {})
    value = _display(current.get("quintile"), ".0f")
    columns = st.columns(5)
    columns[0].metric("Current quintile", value + " / 5" if value != "Unavailable" else value)
    for column, period in zip(columns[1:], ("1m", "3m", "6m", "12m"), strict=True):
        column.metric(period.upper() + " change", _display(current.get("change_" + period), "+.0f"))
    st.caption(
        f"As of {_date(current.get('date'))}. 5 = most favorable; 1 = most unfavorable. "
        "Changes are in quintile points."
    )
    if section.get("history"):
        research_chart(build_trend_figure(section), key="process_trend_history")
    else:
        st.info("Trend-following history is unavailable in the saved workbook.")
    st.caption(
        "The indicator readings are supplied and manually updated in the workbook each month."
    )
    _notes(section)


def _render_ndr(section):
    st.caption(
        "As of "
        + _date(section.get("as_of"))
        + (" (undated saved snapshot)." if not section.get("as_of") else ".")
        + " These model readings are manually updated in the workbook."
    )
    if not section.get("groups"):
        st.info("NDR model readings are unavailable in the saved workbook.")
    for group in section.get("groups", []):
        st.subheader(group["name"])
        rows = [
            {
                "Model": row["model"],
                "Reading": row.get("reading") if row.get("reading") is not None else "Unavailable",
                "Return": row.get("annualized_return"),
                "Return basis": "Next-year median"
                if row.get("return_kind") == "next_year_median"
                else "Annualized gain",
                "Since": str(row["start_year"])
                if row.get("start_year") is not None
                else "Unavailable",
            }
            for row in group.get("rows", [])
        ]
        if rows:
            financial_table(
                base_table_style(pd.DataFrame(rows)).format(
                    {"Return": "{:.2%}"}, na_rep="Unavailable"
                ),
                alt=group["name"] + " model readings and source performance measures",
                column_config={
                    "Model": st.column_config.TextColumn(width=330),
                    "Reading": st.column_config.TextColumn(width=160),
                    "Return": st.column_config.TextColumn(width=75, alignment="right"),
                    "Return basis": st.column_config.TextColumn(width=105),
                    "Since": st.column_config.TextColumn(width=60, alignment="right"),
                },
            )
    if section.get("warnings"):
        st.subheader("Indicators flashing")
        rows = []
        for row in section["warnings"]:
            status = (
                "Unavailable"
                if row.get("triggered") is None or not _number(row.get("current"))
                else "Signal present"
                if row["triggered"]
                else "At or below threshold"
            )
            rows.append(
                {
                    "Model": row["model"],
                    "Prior": row.get("previous"),
                    "Current": row.get("current"),
                    "Threshold": row.get("threshold"),
                    "Status": status,
                }
            )
        financial_table(
            base_table_style(pd.DataFrame(rows)).format(
                {name: "{:.0%}" for name in ("Prior", "Current", "Threshold")},
                na_rep="Unavailable",
            ),
            alt="Prior and current NDR warning percentages with strict signal thresholds",
            column_config={
                "Model": st.column_config.TextColumn(width=310),
                "Prior": st.column_config.TextColumn(width=65, alignment="right"),
                "Current": st.column_config.TextColumn(width=65, alignment="right"),
                "Threshold": st.column_config.TextColumn(
                    width=80,
                    alignment="right",
                    help="Signal only when Current is strictly greater than this value",
                ),
                "Status": st.column_config.TextColumn(width=150),
            },
        )
        st.caption(
            "A warning is present only when the current percentage is strictly above its stated threshold."
        )
    st.caption(
        "Performance measures are copied from the workbook. Next year's median gain is a one-year outcome, "
        "shown separately from annualized gains. Missing source values remain unavailable."
    )
    if "calculator" in section:
        _render_ndr_calculator(section["calculator"] or {})
    _notes(section)


def _source_checks(title, saved, section):
    snapshot = saved["snapshot"]
    issues = [
        issue for issue in snapshot.get("issues", []) if issue.get("sheet") == SOURCE_SHEETS[title]
    ]
    if issues:
        mismatches = any(
            issue.get("kind") == "calculation_mismatch"
            or any(
                word in issue.get("reason", "").lower()
                for word in ("differs", "inconsisten", "mismatch", "disagrees", "nonzero")
            )
            for issue in issues
        )
        explanation = (
            "Source inconsistencies are shown below; calculated panels use the workbook inputs. "
            if mismatches
            else ""
        )
        st.warning(
            f"{len(issues)} source check{'s' if len(issues) != 1 else ''} need attention. "
            + explanation
            + "Missing values remain unavailable; see Workbook source and checks."
        )
    with st.expander("Workbook source and checks"):
        st.write("Source worksheet:", SOURCE_SHEETS[title])
        st.write("Imported (UTC):", saved.get("time") or "Unavailable")
        st.write(
            "Workbook SHA-256:", snapshot.get("sha256") or saved.get("sha256") or "Unavailable"
        )
        st.caption(
            "This page uses saved Excel values and validated workbook calculations. "
            "Refresh Bloomberg in Excel, save the workbook, and leave its configured file accessible for reimport. "
            "A file save does not verify Bloomberg's refresh time."
        )
        if title == "NDR":
            details = [
                {
                    "Group": group["name"],
                    "Model": row["model"],
                    "Source code": row.get("code"),
                    "Source note": row.get("source_note"),
                    "External workbook link": "Yes" if row.get("external_link") else "No",
                }
                for group in section.get("groups", [])
                for row in group.get("rows", [])
                if row.get("code") or row.get("source_note") or row.get("external_link")
            ]
            if details:
                st.markdown("**Model source details**")
                financial_table(pd.DataFrame(details), alt="NDR source codes and workbook notes")
            models = [
                {"group": group["name"], **row}
                for group in section.get("groups", [])
                for row in group.get("rows", [])
            ]
            exports = (("model readings", models), ("warnings", section.get("warnings", [])))
        else:
            exports = (("history", section.get("history", [])),)
        for label, rows in exports:
            if rows:
                st.download_button(
                    "Download " + label + " (CSV)",
                    pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                    file_name=title.lower().replace(" ", "-")
                    + "-"
                    + label.replace(" ", "-")
                    + ".csv",
                    mime="text/csv",
                    key="process_download_" + title + "_" + label,
                )
        if issues:
            financial_table(pd.DataFrame(issues), alt="Source worksheet validation checks")


@st.fragment(run_every="10s")
def _render_process_fragment(title):
    configured = settings.excel_workbook_path
    reimport = st.button(
        "Reimport source workbook",
        key="process_reimport" + title,
        disabled=not bool(configured),
    )
    message = poll_workbook(force=reimport)
    saved = latest_import(success_only=True, profile="process")
    latest = latest_import(False, profile="process")
    st.caption("Source: sponsor's saved Excel workbook · " + str(message))
    if not configured:
        st.warning(
            "Workbook location is not configured. Set EXCEL_WORKBOOK_PATH "
            "to the latest saved workbook to enable updates."
        )
    else:
        file_status = workbook_file_status()
        if file_status.get("error"):
            st.warning(
                "The source workbook is unavailable. The last validated snapshot is retained if available."
            )
    if latest and latest.get("status") == "failed":
        st.warning(
            "The latest workbook import failed. The last validated snapshot is retained if available."
        )
        with st.expander("Latest import issue"):
            st.write(latest.get("error") or "Import validation failed.")
    if not saved or not saved.get("snapshot"):
        st.info(
            "No validated workbook snapshot is available for this page. "
            "Save the updated Excel file and check the configured workbook location."
        )
        return
    section = saved["snapshot"].get("sections", {}).get(title)
    if section is None:
        st.info(
            "This worksheet is unavailable in the last validated snapshot. Import the updated workbook."
        )
        return
    st.caption(
        "Imported "
        + str(saved.get("time") or "time unavailable")
        + " UTC · Bloomberg refresh time unknown"
    )
    {
        "Gold to Oil": _render_gold,
        "NDR": _render_ndr,
        "Intra-Sector Spread": _render_spread,
        "Trend Following": _render_trend,
    }[title](section)
    _source_checks(title, saved, section)


def render_process_section(title):
    """Own these pages even before import, so a public-data fallback cannot replace them."""
    if title not in PAGE_TITLES:
        return False
    _render_process_fragment(title)
    return True
