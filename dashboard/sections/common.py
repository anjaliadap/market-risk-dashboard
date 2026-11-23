"""Shared building blocks for dedicated research pages.

Pages read stored provider observations and the latest validated workbook snapshot. Nothing
here fabricates, interpolates or merges sources: workbook and FRED series keep separate identities,
except where config/providers.json explicitly declares a workbook series equivalent to an
independent one (then the preferred provider's series is used, and labelled as such). Every series
carries its data-source label (src/provenance.py) through to chart captions and tables.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import provenance
from src.analytics.sectors import (
    history_percentile,
    period_tolerance,
    prior_change,
    recession_spans,
    tolerance,
    value_at,
    yoy_change,
    yoy_percent,
)
from src.database.store import history
from src.excel_sync import latest_import, section_state
from src.registry import BY_ID

PRE_PANDEMIC = "2019-12-31"
LOOKBACKS = {"5Y": 5, "10Y": 10, "20Y": 20, "Max": None}


@dataclass
class PageContext:
    title: str
    theme: object
    chart: Callable
    table_view: Callable
    enqueue: Callable


@dataclass(frozen=True)
class Kpi:
    series_id: str
    label: str
    value_format: str = "{:,.2f}"
    delta: str = "yoy_pct"  # yoy_pct | yoy_pp | yoy_bp | yoy_abs | prior
    inverse: bool = False  # True where an increase signals deterioration


def frequency(series_id):
    return BY_ID[series_id]["frequency"]


def independent_series(key):
    """Stored observations for one id, labelled from the URL saved with them (or None)."""
    frame = history(key)
    if frame.empty:
        return None
    series = frame.value.astype(float)
    stored = frame["source"].dropna() if "source" in frame else pd.Series(dtype=object)
    url = stored.iloc[-1] if len(stored) else BY_ID.get(key, {}).get("url")
    return provenance.tag(series, provenance.independent_sources(key, url, BY_ID.get(key)))


def _rank(series):
    order = provenance.config()["preference"]
    names = provenance.providers(provenance.sources_of(series))
    return min((order.index(n) if n in order else len(order) for n in names), default=len(order))


def preferred_series(key, series):
    """Use a declared equivalent workbook series when its provider ranks higher (or is the only one).

    Equivalents are opt-in (config/providers.json) so that, for example, a Bloomberg rate the
    sponsors add to the workbook replaces the FRED download only after someone confirms both
    measure the same thing in the same units.
    """
    equivalent = provenance.config().get("equivalents", {}).get(key)
    if not equivalent:
        return series
    alternative = workbook_series(equivalent["section"], equivalent["series"])
    if alternative.empty:
        return series
    if series is None or _rank(alternative) < _rank(series):
        return alternative
    return series


def load(ids):
    """Value series for every stored id; absent ids are omitted, never synthesized."""
    data = {}
    for key in ids:
        series = preferred_series(key, independent_series(key))
        if series is not None:
            provenance.note_page(provenance.sources_of(series))
            data[key] = series
    return data


def meta_frames(ids):
    return {key: history(key) for key in ids}


def lookback_start(key, default="10Y"):
    choice = st.segmented_control(
        "Chart window", list(LOOKBACKS), default=default, key="lookback_" + key
    )
    years = LOOKBACKS.get(choice or default)
    return None if years is None else pd.Timestamp.today().normalize() - pd.DateOffset(years=years)


def clip(series, start):
    return series if start is None else series.loc[start:]


def yoy(data, key, kind="pct"):
    if key not in data:
        return pd.Series(dtype=float)
    gap = tolerance(frequency(key))
    return yoy_percent(data[key], gap) if kind == "pct" else yoy_change(data[key], gap)


def refresh_controls(ctx, ids):
    ctx.enqueue(ids)
    left, right = st.columns([1, 3])
    if left.button("Refresh stale sources", key="refresh_" + ctx.title):
        ctx.enqueue(ids)
        right.info("Refresh queued in the bounded worker. Rerun to see completed updates.")
    missing = [key for key in ids if history(key).empty]
    if missing:
        st.warning(
            f"UNAVAILABLE · {len(missing)} of {len(ids)} independent series not yet ingested: "
            + ", ".join(missing)
            + ". Run `uv run python -m scripts.refresh_market` and `refresh_macro`. "
            "Dependent tiles and charts stay blank; no substitute values are generated."
        )


def _delta_text(kpi, series):
    gap = tolerance(frequency(kpi.series_id))
    if kpi.delta == "prior":
        change = prior_change(series)
        return None if np.isnan(change) else f"{change:+,.2f} vs prior"
    if kpi.delta == "yoy_pct":
        change = yoy_percent(series, gap).iloc[-1] if len(series) else np.nan
        return None if pd.isna(change) else f"{change:+.1f}% Y/Y"
    change = yoy_change(series, gap).iloc[-1] if len(series) else np.nan
    if pd.isna(change):
        return None
    if kpi.delta == "yoy_bp":
        return f"{change * 100:+.0f} bp Y/Y"
    if kpi.delta == "yoy_abs":
        return f"{change:+,.2f} Y/Y"
    return f"{change:+.2f} pp Y/Y"


def kpi_row(data, kpis):
    columns = st.columns(len(kpis))
    for column, kpi in zip(columns, kpis, strict=True):
        series = data.get(kpi.series_id)
        if series is None or series.dropna().empty:
            column.metric(kpi.label, "—", help="Not ingested")
            column.caption(f"{BY_ID[kpi.series_id]['unit']} · unavailable")
            continue
        s = series.dropna()
        column.metric(
            kpi.label,
            kpi.value_format.format(s.iloc[-1]),
            _delta_text(kpi, s),
            delta_color="inverse" if kpi.inverse else "normal",
            help=f"{BY_ID[kpi.series_id]['name']} · {BY_ID[kpi.series_id]['source']}",
        )
        column.caption(f"{BY_ID[kpi.series_id]['unit']} · {s.index[-1].date()}")


def derived_metric(column, label, series, value_format, unit, delta=None, inverse=False):
    s = series.dropna() if series is not None else pd.Series(dtype=float)
    if s.empty:
        column.metric(label, "—", help="Inputs unavailable")
        column.caption(f"DERIVED · {unit} · unavailable")
        return
    column.metric(
        label,
        value_format.format(s.iloc[-1]),
        delta,
        delta_color="inverse" if inverse else "normal",
    )
    column.caption(f"DERIVED · {unit} · {s.index[-1].date()}")


def shade_recessions(fig, data, start=None):
    if "USREC" not in data:
        return
    for begin, end in recession_spans(data["USREC"]):
        if start is not None and end < start:
            continue
        fig.add_vrect(
            x0=begin, x1=end, fillcolor="#94A3B8", opacity=0.16, line_width=0, layer="below"
        )


def line_figure(title, left, right=None, left_title="", right_title="", zero=False, bars=()):
    """left/right: {label: Series}. ``bars`` lists labels drawn as bars."""
    right = right or {}
    fig = make_subplots(specs=[[{"secondary_y": bool(right)}]])
    for side, group in ((False, left), (True, right)):
        for label, series in group.items():
            s = series.dropna()
            if s.empty:
                continue
            trace = (
                go.Bar(x=s.index, y=s.values, name=label, opacity=0.55)
                if label in bars
                else go.Scatter(x=s.index, y=s.values, name=label, mode="lines")
            )
            trace.meta = {"sources": provenance.sources_of(series)}
            fig.add_trace(trace, secondary_y=side if right else None)
    fig.update_layout(title=title)
    if right:
        fig.update_yaxes(title_text=left_title, secondary_y=False)
        fig.update_yaxes(title_text=right_title, secondary_y=True, showgrid=False)
    else:
        fig.update_yaxes(title_text=left_title)
    if zero:
        fig.add_hline(y=0, line_color="#94A3B8", line_width=1)
    return fig


def has_points(*groups):
    return any(not s.dropna().empty for group in groups if group for s in group.values())


def chart_or_note(ctx, fig, groups, key, note, data=None, start=None):
    if not has_points(*groups):
        st.info("UNAVAILABLE · " + note)
        return
    if data is not None:
        shade_recessions(fig, data, start)
    ctx.chart(fig, key=key)


def indicator_table(data, specs):
    """specs: (series_id, mode) with mode 'pct' (Y/Y %) or 'pp' (Y/Y level change)."""
    rows = []
    for key, mode in specs:
        meta = BY_ID[key]
        series = data.get(key)
        if series is None or series.dropna().empty:
            rows.append({"Series": meta["name"], "Status": "UNAVAILABLE · not ingested"})
            continue
        s = series.dropna()
        gap = tolerance(meta["frequency"])
        change = yoy_percent(s, gap) if mode == "pct" else yoy_change(s, gap)
        baseline = value_at(s, PRE_PANDEMIC, period_tolerance(meta["frequency"]))
        rows.append(
            {
                "Series": meta["name"],
                "Latest": s.iloc[-1],
                "Units": meta["unit"],
                "Observation": s.index[-1].date(),
                "Status": "AVAILABLE / DELAYED",
                "Change vs prior": prior_change(s),
                "Y/Y": change.iloc[-1],
                "Y/Y basis": "%" if mode == "pct" else "level",
                "vs 2019-Q4": s.iloc[-1] - baseline
                if mode == "pp"
                else ((s.iloc[-1] / baseline - 1) * 100 if baseline and baseline > 0 else np.nan),
                "Percentile since 2000": history_percentile(s, "2000-01-01"),
                "Source": provenance.describe(provenance.sources_of(series)) or "Unknown",
                "Link": meta["url"],
            }
        )
    return pd.DataFrame(rows)


def snapshot_table(ctx, data, specs, filename):
    table = indicator_table(data, specs)
    ctx.table_view(table, hide_index=True)
    st.caption(
        "Y/Y uses the last observation on/before the date 12 months earlier, within a "
        "frequency-specific tolerance. 'vs 2019-Q4' is a level difference for rates and a "
        "percent change for levels. Percentiles are empirical ranks over retained history "
        "(requested since 2000)."
    )
    st.download_button(
        "Export indicator table (CSV with source metadata)",
        table.to_csv(index=False),
        filename,
        "text/csv",
        key="export_" + filename,
    )


# --- Workbook helpers ------------------------------------------------------------------------


def workbook_section(title):
    saved = latest_import(success_only=True)
    if not saved or not saved.get("snapshot"):
        return None
    return saved["snapshot"]["sections"].get(title)


def section_notice(title):
    """Warn when a section's workbook tab was rejected or is shown from an earlier import."""
    state = section_state(title)
    if state["state"] == "retained":
        since = str(state["imported_at"])[:16].replace("T", " ")
        st.warning(
            f"OUT OF DATE · The latest workbook's {title} tab did not pass validation "
            f"({state['reason']}). Showing the data kept from the import of {since} UTC."
        )
    elif state["state"] == "rejected":
        st.warning(
            f"UNAVAILABLE · The {title} workbook tab was not imported because it did not pass "
            f"validation: {state['reason']}. See Workbook Administration."
        )
    return state


def workbook_series(title, series_id):
    """Saved historical workbook points for one mapped series (forward estimates excluded)."""
    section = workbook_section(title)
    if not section:
        return pd.Series(dtype=float)
    for chart in section["charts"]:
        for series in chart["series"]:
            if series["id"] != series_id:
                continue
            points = [
                (pd.Timestamp(p["date"]), p["value"])
                for p in series["points"]
                if p["value"] is not None and not p["forward"]
            ]
            if not points:
                return pd.Series(dtype=float)
            dates, values = zip(*points, strict=True)
            out = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float).sort_index()
            labels = saved_sources(series)
            provenance.note_page(labels)
            return provenance.tag(out, labels)
    return pd.Series(dtype=float)


def saved_sources(item):
    """Sources recorded at import for a workbook series or table (older snapshots: generic)."""
    return item.get("sources") or [provenance.source("workbook:unknown")]


def workbook_cell(title, coordinate):
    """Saved scalar from a mapped workbook table cell, or None."""
    section = workbook_section(title)
    if not section:
        return None
    for table in section["tables"]:
        for row in table["rows"]:
            for cell in row:
                if cell.get("cell") == coordinate:
                    value = cell.get("value")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        return float(value)
                    return None
    return None


def cross_check(ctx, data, title, pairs, key):
    """Overlay sponsor workbook series against independent FRED series on separate axes."""
    rows, shown = [], False
    for workbook_id, workbook_label, fred_id in pairs:
        saved = workbook_series(title, workbook_id)
        independent = data.get(fred_id, pd.Series(dtype=float))
        if saved.empty or independent.empty:
            rows.append(
                {
                    "Workbook series": workbook_label,
                    "Independent series": BY_ID[fred_id]["name"],
                    "Status": "UNAVAILABLE · workbook snapshot or FRED history missing",
                }
            )
            continue
        rows.append(
            {
                "Workbook series": workbook_label,
                "Workbook latest": saved.iloc[-1],
                "Workbook date": saved.index[-1].date(),
                "Independent series": BY_ID[fred_id]["name"],
                "Independent latest": independent.iloc[-1],
                "Independent date": independent.index[-1].date(),
                "Independent units": BY_ID[fred_id]["unit"],
                "Status": "AVAILABLE",
            }
        )
        fig = line_figure(
            f"Cross-check · {workbook_label} (workbook) vs {BY_ID[fred_id]['name']} (FRED)",
            {"Workbook · " + workbook_label: saved},
            {"FRED · " + fred_id: independent},
            "Workbook units",
            BY_ID[fred_id]["unit"],
        )
        ctx.chart(fig, key=f"{key}_{workbook_id}")
        shown = True
    ctx.table_view(pd.DataFrame(rows), hide_index=True)
    st.caption(
        "Separate axes because PCM - Monthly Market & Risk Monitor Bloomberg tickers and FRED producers can differ in "
        "population, units and seasonal adjustment. Series are never merged or substituted."
        + ("" if shown else " Import the workbook and ingest FRED to populate the overlay.")
    )


def render_workbook(title, render_section):
    if workbook_section(title) is None:
        if section_notice(title)["state"] != "rejected":
            st.info(
                "No validated workbook snapshot for this section. Configure EXCEL_WORKBOOK_PATH "
                "and import from Workbook Administration. Independent analytics remain available."
            )
        return
    render_section(title)  # Shows the out-of-date notice itself when the data is retained.


def current_sources(key):
    """Live data sources for one series id (follows declared equivalents); [] if not ingested."""
    series = preferred_series(key, independent_series(key))
    return [] if series is None else provenance.sources_of(series)


def current_source(key):
    """Live data-source label for one series id."""
    series = preferred_series(key, independent_series(key))
    if series is None:
        return "Not yet ingested"
    return provenance.describe(provenance.sources_of(series)) or "Unknown"


def sources_table(ctx, ids, notes):
    for note in notes:
        st.markdown("- " + note)
    ctx.table_view(
        pd.DataFrame(
            [
                {
                    "Series": BY_ID[k]["name"],
                    "ID": k,
                    "Units": BY_ID[k]["unit"],
                    "Frequency": BY_ID[k]["frequency"],
                    "Data source": current_source(k),
                    "Link": BY_ID[k]["url"],
                }
                for k in ids
            ]
        ),
        hide_index=True,
    )


def page_tabs(title, independent_first_label="Independent analytics"):
    """Workbook tab leads when a validated snapshot exists; otherwise analytics lead."""
    labels = [
        "PCM - Monthly Market & Risk Monitor",
        independent_first_label,
        "Indicators",
        "Methodology & sources",
    ]
    if workbook_section(title) is None:
        labels = [labels[1], labels[0], labels[2], labels[3]]
    tabs = dict(zip(labels, st.tabs(labels), strict=True))
    return (
        tabs["PCM - Monthly Market & Risk Monitor"],
        tabs[independent_first_label],
        tabs["Indicators"],
        tabs["Methodology & sources"],
    )
