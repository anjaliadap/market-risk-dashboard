"""Shared UI for the Recession, VIX & Options, Demand, Supply and Financing pages.

Adds the pieces those pages need beyond ``common``: rule-based checklist tables with a red-signal
score, raw workbook table cells, and an append-only log for analyst-sourced observations
(GPU rental quotes, data-center capacity, lead times) that have no machine-readable feed.
"""

import json
import uuid
from datetime import UTC, date, datetime

import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from dashboard.sections.common import line_figure, workbook_section
from dashboard.styles.theme import (
    AMBER,
    NEGATIVE,
    NEGATIVE_BG,
    POSITIVE,
    POSITIVE_BG,
    WARNING_BG,
    base_table_style,
)
from src.analytics.signals import checks_frame, score
from src.database import store
from src.database.store import ResearchRecord

# --- Checklists ----------------------------------------------------------------------------------


def signal_style(value):
    text = str(value)
    if text == "RED":
        return f"color: {NEGATIVE}; background-color: {NEGATIVE_BG}; font-weight: 700"
    if text == "Not red":
        return f"color: {POSITIVE}; background-color: {POSITIVE_BG}"
    if text.startswith("UNAVAILABLE"):
        return f"color: {AMBER}; background-color: {WARNING_BG}"
    return ""


def checklist(ctx, checks, key, label="signals", extra_columns=None):
    """Score tiles plus the styled rule table. Returns the frame for reuse/export."""
    red, evaluated, total = score(checks)
    a, b, c = st.columns(3)
    a.metric(f"Red {label}", f"{red} of {evaluated}" if evaluated else "—")
    b.metric(
        "Share red",
        f"{red / evaluated:.0%}" if evaluated else "—",
        help="Red signals divided by evaluated signals. Unavailable items are excluded, not "
        "assumed green.",
    )
    c.metric("Coverage", f"{evaluated} of {total} evaluated")
    frame = checks_frame(checks)
    if extra_columns:
        for name, values in extra_columns.items():
            frame.insert(5, name, values)
    styled = base_table_style(frame).map(signal_style, subset=["Signal"])
    ctx.table_view(styled, hide_index=True, alt=f"{ctx.title} rule-based {label}")
    st.download_button(
        "Export checklist (CSV with rules and sources)",
        frame.to_csv(index=False),
        f"{key}.csv",
        "text/csv",
        key=f"export_{key}",
    )
    return frame


# --- Workbook helpers ----------------------------------------------------------------------------


def workbook_cells(title):
    """{coordinate: raw saved value} for every mapped table cell (text kept as text)."""
    section = workbook_section(title)
    if not section:
        return {}
    return {
        cell["cell"]: cell.get("value")
        for table in section["tables"]
        for row in table["rows"]
        for cell in row
    }


def workbook_reference(title, chart_id):
    """Return (latest_reported_date, has_forward_points) for a mapped workbook chart."""
    section = workbook_section(title)
    if not section:
        return None, False
    for chart in section["charts"]:
        if chart["id"] != chart_id:
            continue
        reported = [s.get("latest_reported") for s in chart["series"] if s.get("latest_reported")]
        forward = any(p["forward"] for s in chart["series"] for p in s["points"])
        return (max(reported) if reported else None), forward
    return None, False


def add_reference(fig, y, label, dash="dash"):
    fig.add_hline(
        y=y,
        line_dash=dash,
        line_width=1,
        line_color="#64748B",
        annotation_text=label,
        annotation_position="top left",
    )
    return fig


# --- Analyst-sourced observations ----------------------------------------------------------------

DATASETS = {
    "gpu_pricing": {
        "label": "GPU rental prices",
        "unit": "USD per GPU-hour",
        "dimensions": {
            "chip": [
                "H100 SXM",
                "H100 PCIe",
                "H200",
                "B200",
                "GB200",
                "A100 80GB",
                "L40S",
                "MI300X",
            ],
            "pricing_type": ["On-demand", "Spot", "Contracted / reserved"],
            "provider": None,
        },
        "series_by": ["chip", "pricing_type"],
    },
    "dc_capacity": {
        "label": "Data-center capacity",
        "unit": "MW",
        "dimensions": {
            "market": None,
            "status": ["Operational", "Under construction", "Planned"],
        },
        "series_by": ["market", "status"],
    },
    "dc_vacancy": {
        "label": "Data-center vacancy / available supply",
        "unit": "percent (vacancy) or MW (available)",
        "dimensions": {"market": None, "measure": ["Vacancy rate (%)", "Available supply (MW)"]},
        "series_by": ["market", "measure"],
    },
    "lead_times": {
        "label": "Supply-chain lead times",
        "unit": "weeks",
        "dimensions": {
            "component": [
                "Large power transformers",
                "Gas turbines",
                "Switchgear",
                "Backup generators",
                "AI servers / GPUs",
                "HBM memory",
            ]
        },
        "series_by": ["component"],
    },
    "semis_billings": {
        "label": "Semiconductor billings (SIA/WSTS)",
        "unit": "USD billions, 3-month moving average",
        "dimensions": {
            "region": ["Worldwide", "Americas", "Asia Pacific", "Europe", "Japan", "China"]
        },
        "series_by": ["region"],
    },
}


def observations(dataset):
    with Session(store.engine) as session:
        rows = session.scalars(
            select(ResearchRecord)
            .where(ResearchRecord.kind == "analyst:" + dataset)
            .order_by(ResearchRecord.id)
        ).all()
        records = [json.loads(r.payload) for r in rows]
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.sort_values("date")


def validate(dataset, records):
    """Return (clean records, errors). Every record needs a date, positive value and source URL."""
    spec = DATASETS[dataset]
    ok, errors = [], []
    for i, record in enumerate(records, start=1):
        try:
            when = pd.Timestamp(record["date"]).date()
            value = float(record["value"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"Row {i}: date and numeric value required")
            continue
        url = str(record.get("source_url") or "").strip()
        if not url.startswith(("https://", "http://")):
            errors.append(f"Row {i}: source_url must be an http(s) link")
            continue
        if value < 0:
            errors.append(f"Row {i}: value must be non-negative")
            continue
        if when > date.today():
            errors.append(f"Row {i}: observation date is in the future")
            continue
        missing = [d for d in spec["dimensions"] if not str(record.get(d) or "").strip()]
        if missing:
            errors.append(f"Row {i}: missing {', '.join(missing)}")
            continue
        clean = {d: str(record[d]).strip() for d in spec["dimensions"]}
        clean.update(
            date=when.isoformat(),
            value=value,
            unit=spec["unit"],
            source_url=url,
            note=str(record.get("note") or "").strip(),
            entered_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        ok.append(clean)
    return ok, errors


def store_observations(dataset, records):
    with Session(store.engine) as session, session.begin():
        for record in records:
            session.add(
                ResearchRecord(
                    kind="analyst:" + dataset, name=uuid.uuid4().hex, payload=json.dumps(record)
                )
            )


def analyst_log(ctx, dataset, key):
    """Entry form, CSV import/export, history table and chart for one analyst dataset."""
    spec = DATASETS[dataset]
    frame = observations(dataset)
    st.markdown(f"**{spec['label']}** · {spec['unit']}")
    if frame.empty:
        st.info(
            "UNAVAILABLE · No analyst-sourced observations recorded yet. Add quotes below with a "
            "source link; nothing is scraped or estimated automatically."
        )
    else:
        series = {}
        for labels, group in frame.groupby(spec["series_by"]):
            name = " · ".join(labels if isinstance(labels, tuple) else (labels,))
            series[name] = group.groupby("date")["value"].median()
        ctx.chart(
            line_figure(f"ANALYST-SOURCED · {spec['label']}", series, left_title=spec["unit"]),
            key=f"{key}_chart",
        )
        latest = frame.sort_values("date").groupby(spec["series_by"]).tail(1)
        ctx.table_view(
            latest[["date", *spec["dimensions"], "value", "unit", "source_url", "note"]].rename(
                columns={"source_url": "Source"}
            ),
            hide_index=True,
        )
        st.download_button(
            "Export full history (CSV)",
            frame.to_csv(index=False),
            f"{dataset}.csv",
            "text/csv",
            key=f"{key}_export",
        )
    with st.expander("Add an observation"), st.form(f"{key}_form", clear_on_submit=True):
        record = {}
        columns = st.columns(len(spec["dimensions"]) + 2)
        for column, (name, options) in zip(columns, spec["dimensions"].items(), strict=False):
            label = name.replace("_", " ").capitalize()
            record[name] = (
                column.selectbox(label, options, key=f"{key}_{name}")
                if options
                else column.text_input(label, key=f"{key}_{name}")
            )
        record["date"] = columns[-2].date_input(
            "Observation date", value=date.today(), key=f"{key}_date"
        )
        record["value"] = columns[-1].number_input(
            f"Value ({spec['unit']})", min_value=0.0, format="%.3f", key=f"{key}_value"
        )
        record["source_url"] = st.text_input("Source URL (required)", key=f"{key}_url")
        record["note"] = st.text_input("Note (term, region, configuration)", key=f"{key}_note")
        if st.form_submit_button("Save observation"):
            clean, errors = validate(dataset, [record])
            if errors:
                st.error("; ".join(errors))
            else:
                store_observations(dataset, clean)
                st.success("Saved. Records are append-only for auditability.")
                st.rerun()
    with st.expander("Import from CSV"):
        template = ",".join(["date", *spec["dimensions"], "value", "source_url", "note"])
        st.caption(f"Required columns: `{template}`. Invalid rows are rejected with a reason.")
        upload = st.file_uploader("CSV file", type="csv", key=f"{key}_upload")
        if upload is not None and st.button("Import rows", key=f"{key}_import"):
            records = pd.read_csv(upload).to_dict("records")
            clean, errors = validate(dataset, records)
            if clean:
                store_observations(dataset, clean)
            st.write(f"Imported {len(clean)} rows; rejected {len(errors)}.")
            for error in errors[:20]:
                st.caption(error)
