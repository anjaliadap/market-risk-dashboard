import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from dashboard.excel_views import render_administration, render_section, synchronization_status
from dashboard.sections import RENDERERS, PageContext
from dashboard.styles.theme import (
    financial_table,
    page_header,
    research_chart,
    theme_for,
)
from src.analytics.core import (
    drawdown,
    historical_comparison,
    moving_average,
    period_changes,
    range_distance,
    relative,
    scenario,
    volatility,
)
from src.database.store import Job, ResearchRecord, engine, history, initialize
from src.refresh import enqueue
from src.registry import BY_ID, REGISTRY

st.set_page_config(page_title="Market & Risk Intelligence", page_icon="◈", layout="wide")
initialize()
synchronization_status()
PAGES = json.loads((Path(__file__).resolve().parents[1] / "config/pages.json").read_text())
MAPPING = {
    "Executive Overview": ["SP500", "DGS10", "VIXCLS", "UNRATE"],
    "Market Data": [
        "SP500",
        "DGS2",
        "DGS5",
        "DGS10",
        "DGS30",
        "MORTGAGE30US",
        "VIXCLS",
        "DCOILWTICO",
        "DCOILBRENTEU",
        "DHHNGSP",
    ],
    "Bear Market": ["VIXCLS", "BAMLH0A0HYM2", "DGS2", "DGS10"],
    "S&P vs Bonds": ["DGS10"],
    "S&P Relative": ["SP500", "DCOILWTICO"],
    "VIX & Options": ["VIXCLS"],
    "Energy": ["DCOILWTICO", "DCOILBRENTEU", "DHHNGSP"],
    "Recession": [
        "DGS2",
        "DGS10",
        "UNRATE",
        "ICSA",
        "CPIAUCSL",
        "INDPRO",
        "T5YIE",
        "T10YIE",
        "BAMLH0A0HYM2",
        "GDP",
        "USREC",
    ],
}
BLOCKERS = {
    "Market Data": "Remaining indices, all 11 sector histories, breadth, MOVE and metals need verified permitted feeds. No ETF substitutions. Rates are changes in basis points; VIX changes are index points. Spot commodity returns are not futures returns.",
    "Bear Market": "Historical peak comparison requires sponsor event dates and publication-aligned history. No aggregate predictive score is claimed.",
    "S&P vs Bonds": "Earnings-yield spread requires dated index earnings/P-E history. A simple yield spread is not a modeled equity risk premium.",
    "S&P 500 Fundamentals": "Official index aggregates require a licensed dataset; constituent medians would not be equivalent.",
    "Margin Debt": "FINRA margin history and comparable market capitalization ingestion are not implemented. GDP is in billions; FINRA figures require unit alignment.",
    "S&P Relative": "Gold history is not connected. Index/oil ratios mix index points and USD per barrel and are research ratios, not investable returns.",
    "Gold to Oil": "Verified USD gold spot history is required. No futures splice or synthetic observation is used.",
    "Bull vs Bear": "AAII history requires permitted access. Conditional-return studies require publication dates and overlap controls.",
    "VIX & Options": "MOVE and put/call feeds are not connected; licensing and history must be verified.",
    "BTC": "Exchange/reference-currency provider and history are not yet verified. No synthetic price feed.",
    "Energy": "Spot prices only. EIA inventory, production, utilization, storage and seasonal balance ingestion remain unimplemented.",
    "Recession": "Current revised observations are unsuitable for real-time backtests. ALFRED vintages, GDPNow, policy futures and calibrated probabilities are not implemented.",
    "Demand": "SEC company facts and industry feeds are not yet integrated. Cloud revenue is not AI-specific revenue.",
    "Forecasting": "SEC filed capex and cash-flow data are not integrated. Scenarios below are explicit analyst assumptions, not company forecasts.",
}


def render(title):
    if title == "Workbook Administration":
        render_administration()
        return
    theme = theme_for(title, PAGES)
    page_header(title, theme)

    def table_view(frame, **kwargs):
        financial_table(frame, theme, **kwargs)

    def chart(figure, **kwargs):
        research_chart(figure, theme, **kwargs)

    if title in RENDERERS:
        RENDERERS[title](PageContext(title, theme, chart, table_view, enqueue), render_section)
        return
    excel_primary = render_section(title)
    if excel_primary:
        if title not in MAPPING:
            return
        if not st.checkbox(
            "Show independent FRED observations for comparison", key="independent_" + title
        ):
            return
    if title == "Supply":
        st.info(
            "No workbook source exists for AI Supply. Capacity, vacancy, supply-chain lead times and GPU rental prices require independently verified sources; see the integration audit for the source strategy."
        )
        return
    if title in BLOCKERS and not excel_primary:
        st.warning("Coverage limitation · " + BLOCKERS[title])
    if title == "Data Sources & System Status":
        st.subheader("Source registry")
        table_view(pd.DataFrame(REGISTRY), hide_index=True)
        st.subheader("Recent ingestion activity")
        with Session(engine) as session:
            jobs = session.scalars(select(Job).order_by(Job.started_at.desc()).limit(100)).all()
            table_view(
                pd.DataFrame(
                    [
                        {
                            "series": j.series_id,
                            "time": j.started_at,
                            "status": j.status,
                            "new_versions": j.count,
                            "error": j.error,
                        }
                        for j in jobs
                    ]
                )
            )
        st.download_button(
            "Download source registry", json.dumps(REGISTRY, indent=2), "sources.json"
        )
        return
    if title == "Forecasting":
        st.warning(
            "ASSUMPTIONS · Values entered below are illustrative analyst inputs, not reported company figures."
        )
        a, b = st.columns(2)
        capex = a.number_input("Starting capex (assumed USD billions)", min_value=0.0, value=100.0)
        ocf = b.number_input(
            "Starting operating cash flow (assumed USD billions)", min_value=0.0, value=150.0
        )
        for label, cg, og in [
            ("Base", 0.10, 0.10),
            ("Optimistic", 0.05, 0.15),
            ("Downside", 0.20, 0.02),
        ]:
            with st.expander(label, expanded=label == "Base"):
                c = (
                    st.number_input(
                        "Capex growth (%)", value=cg * 100, key=label + "c", min_value=-99.0
                    )
                    / 100
                )
                o = (
                    st.number_input(
                        "OCF growth (%)", value=og * 100, key=label + "o", min_value=-99.0
                    )
                    / 100
                )
                frame = scenario(capex, ocf, c, o)
                chart(
                    px.line(
                        frame,
                        x="year",
                        y=["capex", "operating_cash_flow", "free_cash_flow"],
                        title=label + " · assumed USD billions",
                    ),
                    width="stretch",
                )
                table_view(frame, hide_index=True)
    ids = MAPPING.get(title, [])
    if not ids:
        if title == "Forecasting":
            return
        st.warning(
            "UNAVAILABLE · No verified observations connected for this page. See coverage report for outstanding work."
        )
        return
    enqueue(ids)
    if st.button("Check freshness / refresh stale sources"):
        enqueue(ids)
        st.info(
            "Refresh queued in a single bounded worker. Existing valid observations remain available; rerun to see completed updates."
        )
    st.caption(
        "Retrieval cadence: at most daily after success; failed attempts cool down for one hour. Observation age and source publication lag are separate from retrieval freshness."
    )
    rows = []
    histories = {}
    for key in ids:
        meta = BY_ID[key]
        h = history(key)
        if h.empty:
            rows.append(
                {
                    "Series": meta["name"],
                    "Status": "UNAVAILABLE · not ingested",
                    "Source": meta["url"],
                }
            )
            continue
        histories[key] = h
        s = h.value
        rate = key.startswith("DGS") or key == "MORTGAGE30US"
        changes = (
            period_changes(s, basis_points=rate, max_gap_days=10)
            if key
            in {
                "SP500",
                "DGS2",
                "DGS5",
                "DGS10",
                "DGS30",
                "MORTGAGE30US",
                "VIXCLS",
                "DCOILWTICO",
                "DCOILBRENTEU",
                "DHHNGSP",
            }
            else {}
        )
        if key == "VIXCLS":
            changes = {
                k: (v / 100) * s.iloc[-1] / (1 + v / 100) if pd.notna(v) else v
                for k, v in changes.items()
            }
        extra = {}
        if key == "SP500":
            for window in [50, 200]:
                average = moving_average(s, window).iloc[-1]
                extra[f"Distance to {window}-DMA (%)"] = (
                    (s.iloc[-1] / average - 1) * 100 if pd.notna(average) else float("nan")
                )
            extra.update(range_distance(s))
        rows.append(
            {
                **extra,
                "Series": meta["name"],
                "Latest": s.iloc[-1],
                "Units": meta["unit"],
                "Observation": s.index[-1].date(),
                "Retrieved (UTC)": str(h.retrieved_at.iloc[-1]),
                "Release": "Not supplied",
                "Status": "AVAILABLE / DELAYED",
                "Change units": "bp" if rate else "points" if key == "VIXCLS" else "%",
                **changes,
                "Source": meta["url"],
            }
        )
    if histories:
        st.subheader("Latest observations")
        columns = st.columns(min(4, len(histories)))
        for column, (series_id, frame) in zip(columns, list(histories.items())[:4], strict=False):
            column.metric(BY_ID[series_id]["name"], f"{frame.value.iloc[-1]:,.2f}")
            column.caption(f"{BY_ID[series_id]['unit']} · {frame.index[-1].date()}")
    st.subheader("Research snapshot")
    table = pd.DataFrame(rows)
    table_view(table, hide_index=True, width="stretch")
    st.download_button(
        "Export research table (CSV with source metadata)",
        table.to_csv(index=False),
        title.lower().replace(" ", "_") + ".csv",
        "text/csv",
    )
    if not histories:
        st.warning(
            "No saved observations. Run the documented refresh command, or request a freshness check above. Source failure never generates substitute values."
        )
        return
    if "DGS10" in histories and "DGS2" in histories:
        curve = pd.concat(
            [histories["DGS10"].value.rename("10y"), histories["DGS2"].value.rename("2y")], axis=1
        ).dropna()
        if len(curve):
            spread = (curve["10y"] - curve["2y"]) * 100
            chart(
                px.line(spread, title="DERIVED · 10-year minus 2-year Treasury spread (bp)"),
                width="stretch",
            )
    if title == "S&P Relative" and {"SP500", "DCOILWTICO"}.issubset(histories):
        research_ratio = relative(histories["SP500"].value, histories["DCOILWTICO"].value)
        chart(
            px.line(
                research_ratio, title="DERIVED · S&P price index points / WTI spot USD per barrel"
            ),
            width="stretch",
        )
    if title == "Recession" and "UNRATE" in histories:
        unemployment = histories["UNRATE"].value
        average = unemployment.rolling(3).mean()
        sahm = average - average.rolling(12).min()
        chart(
            px.line(sahm, title="DERIVED · Sahm-style unemployment gap (percentage points)"),
            width="stretch",
        )
        st.caption(
            "Three-month mean unemployment minus minimum three-month mean over trailing 12 months. Current revised series; not the official real-time Sahm indicator or a recession probability."
        )
    with Session(engine) as session:
        events = session.scalars(
            select(ResearchRecord).where(ResearchRecord.kind == "historical_event")
        ).all()
        event_definitions = [json.loads(event.payload) for event in events]
    if title in {"Bear Market", "Recession"}:
        with st.expander("Historical reference comparisons"):
            if not event_definitions:
                st.info(
                    "No reference dates imported. Use the documented historical event CSV template; no historical dates are invented."
                )
            else:
                names = st.multiselect(
                    "Reference events",
                    [event["name"] for event in event_definitions],
                    default=[event["name"] for event in event_definitions],
                )
                dates = [event["date"] for event in event_definitions if event["name"] in names]
                stats = [
                    {
                        "Series": BY_ID[k]["name"],
                        **historical_comparison(
                            h.value, dates, 45 if BY_ID[k]["frequency"] == "monthly" else 7
                        ),
                    }
                    for k, h in histories.items()
                ]
                table_view(pd.DataFrame(stats), hide_index=True)
                st.caption(
                    "Descriptive reference-date comparisons use bounded observation-date alignment, not publication-aware backtests. Not evidence of predictive power."
                )
    st.subheader("Historical analysis")
    key = st.selectbox("Historical series", list(histories), format_func=lambda k: BY_ID[k]["name"])
    h = histories[key]
    start = st.date_input(
        "Chart start",
        value=max(h.index[0].date(), (h.index[-1] - pd.DateOffset(years=5)).date()),
        min_value=h.index[0].date(),
        max_value=h.index[-1].date(),
    )
    selected = h.loc[str(start) :]
    chart(
        px.line(
            selected,
            x=selected.index,
            y="value",
            labels={"value": BY_ID[key]["unit"], "x": "Observation date"},
        ),
        width="stretch",
    )
    if key == "SP500":
        chart(
            px.line(
                drawdown(h.value).loc[str(start) :], title="DERIVED · price-index drawdown (%)"
            ),
            width="stretch",
        )
        chart(
            px.line(
                volatility(h.value).loc[str(start) :],
                title="DERIVED · 21-session annualized volatility (%)",
            ),
            width="stretch",
        )
    if title == "Market Data":
        yields = [(int(k[3:]), history(k)) for k in ["DGS2", "DGS5", "DGS10", "DGS30"]]
        if all(not h.empty for _, h in yields):
            common = set.intersection(*(set(h.index) for _, h in yields))
            if common:
                date = max(common)
                chart(
                    px.line(
                        x=[n for n, _ in yields],
                        y=[h.loc[date, "value"] for _, h in yields],
                        markers=True,
                        labels={"x": "Maturity (years)", "y": "Yield (%)"},
                        title=f"Treasury curve · common observation {date.date()}",
                    ),
                    width="stretch",
                )
        st.caption(
            "These independent FRED calculations measure index-price distance from its trailing average. The sponsor workbook's Market Data charts measure constituent breadth and are shown separately."
        )
    with st.expander("Source, methodology and observation metadata"):
        st.json(BY_ID[key])
        st.write(
            "Period returns: endpoint / baseline − 1. Calendar-month targets use last observation on/before target, maximum 10-day gap. YTD baseline is prior calendar year-end. Price-index returns exclude dividends; commodity series here are spot prices, without futures rolls. Unavailable baselines remain blank. Published dates are unknown, never inferred from observation dates. Retrieval vintages do not establish real-time macro vintages."
        )
        table_view(h.tail(10), hide_index=False)
        st.download_button(
            "Export selected history with metadata", h.to_csv(), key + ".csv", "text/csv"
        )


def page(title):
    return st.Page(
        lambda: render(title),
        title=title,
        url_path=title.lower().replace(" ", "-").replace("&", "and"),
    )


navigation = {
    "Home": [page("Executive Overview")],
    **{group: [page(t) for t in titles] for group, titles in PAGES.items()},
    "Research operations": [page("Data Sources & System Status"), page("Workbook Administration")],
}
st.navigation(navigation).run()
