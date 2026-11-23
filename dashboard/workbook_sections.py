"""The three requested workbook sections, using the host app's UI and store."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from dashboard.styles.theme import Theme, financial_table, research_chart
from src.analytics.btc import coverage_snapshot
from src.analytics.margin_debt import peak_comparison, quarterly_ratio
from src.analytics.sentiment import decile_returns, spread_history
from src.database.store import Job, engine, history, source_metadata
from src.providers.workbook_sections import AAII_IDS, STRATEGY_IDS
from src.refresh import enqueue
from src.registry import BY_ID

PAGE_IDS = {
    "Margin Debt": ["FINRA_MARGIN_DEBT", "GDP", "BOGZ1LM883164115Q"],
    "Bull vs Bear": list(AAII_IDS),
    "BTC": ["COINBASE_BTC_SPOT", *STRATEGY_IDS],
}


def _status_rows(ids, histories):
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows = []
    with Session(engine) as session:
        for key in ids:
            meta = BY_ID[key]
            h = histories.get(key)
            job = session.scalar(
                select(Job).where(Job.series_id == key).order_by(Job.started_at.desc()).limit(1)
            )
            row = {"Series": meta["name"], "Units": meta["unit"], "Source": meta["url"]}
            if h is None or h.empty:
                row.update(Status="UNAVAILABLE", Observation="—", Latest=None)
            else:
                date = h.index[-1]
                shown_date = (
                    date.to_period("Q").end_time.date()
                    if meta["frequency"] == "quarterly"
                    else date.date()
                )
                if key in STRATEGY_IDS:
                    component_date = source_metadata(key).get("component_as_of_dates", {}).get(key)
                    if component_date:
                        shown_date = pd.Timestamp(component_date).date()
                age = (now - pd.Timestamp(shown_date)).days
                status = "AVAILABLE / DELAYED"
                if age > meta.get("stale_days", 200 if meta["frequency"] == "quarterly" else 14):
                    status = "STALE · saved observations"
                if key == "COINBASE_BTC_SPOT":
                    quote = h.published_at.iloc[-1]
                    if pd.isna(quote) or now - pd.Timestamp(quote).tz_localize(None) > pd.Timedelta(
                        minutes=15
                    ):
                        status = "STALE · saved quote"
                row.update(
                    Status=status,
                    Observation=str(shown_date),
                    Latest=h.value.iloc[-1],
                    **{
                        "Retrieved (UTC)": str(h.retrieved_at.iloc[-1]),
                        "Source time (UTC)": str(h.published_at.iloc[-1])
                        if pd.notna(h.published_at.iloc[-1])
                        else "Not supplied",
                    },
                )
            if job is not None:
                row["Last attempt (UTC)"] = str(job.started_at)
                if job.status == "failed":
                    row["Status"] += " · refresh failed"
                    row["Error"] = job.error
            rows.append(row)
    return pd.DataFrame(rows)


def _download(frame, name):
    st.download_button(
        "Download calculation history", frame.to_csv(), name + ".csv", "text/csv", key=name
    )


def _margin(histories, theme):
    debt_frame = histories.get("FINRA_MARGIN_DEBT")
    if debt_frame is None:
        st.info(
            "FINRA observations are being requested. Refresh status below shows any source failure."
        )
        return
    debt = debt_frame.value
    st.metric("Customer margin debit balances", f"${debt.iloc[-1] / 1000:,.1f} billion")
    st.caption(
        f"Reference month {debt.index[-1]:%B %Y} · FINRA publishes monthly, usually in the following month."
    )
    st.subheader("Historical peak and trough comparisons")
    financial_table(peak_comparison(debt.iloc[-1]), theme)
    st.caption(
        "Historical peaks and troughs are the workbook's rounded reference figures, USD billions. Current comparisons use the 2021 peak (USD 919bn) and subsequent trough (USD 607bn). These references do not identify new cycles automatically."
    )
    st.info(
        "Market-cap comparison uses Federal Reserve domestic public corporate equities at quarter end. Its coverage and frequency differ from the workbook's monthly Wilshire 5000 capitalization."
    )
    columns = st.columns(2)
    for column, key, label, unit, start in [
        (columns[0], "GDP", "Margin debt / nominal GDP", "USD billions", "2000-01-01"),
        (
            columns[1],
            "BOGZ1LM883164115Q",
            "Margin debt / Fed public equity value (proxy)",
            "USD millions",
            "1997-01-01",
        ),
    ]:
        with column:
            if key not in histories:
                st.warning(
                    f"{BY_ID[key]['name']} is unavailable; ratio awaits a valid denominator."
                )
                continue
            frame = quarterly_ratio(debt, histories[key].value, denominator_unit=unit, start=start)
            if frame.empty:
                st.warning("No matching quarter-end source periods.")
                continue
            st.metric(label, f"{frame.ratio_pct.iloc[-1]:.2f}%")
            st.caption(
                f"Matched quarter end {frame.index[-1]:%d %b %Y} · {len(frame)} observations"
            )
            figure = go.Figure()
            for field, name in [("ratio_pct", "Ratio"), ("historical_mean_pct", "Historical mean")]:
                figure.add_trace(
                    go.Scatter(x=frame.index, y=frame[field], name=name, connectgaps=False)
                )
            figure.update_yaxes(title="Percent", ticksuffix="%")
            research_chart(figure, theme)
            _download(frame, "margin_" + key.lower())
    st.caption(
        "Ratios match the quarter-end margin month to the same reported quarter. GDP is nominal USD billions at a seasonally adjusted annual rate; FINRA and Fed equity levels are USD millions. No missing month is carried forward. Historical means use all matched observations shown by each source, and current revised GDP/Fed data are descriptive."
    )


def _sentiment(histories, theme):
    if not {"AAII_BULLISH", "AAII_BEARISH"}.issubset(histories):
        st.info(
            "The AAII public workbook is being requested. No substitute sentiment values are used."
        )
        return
    frame = spread_history(histories["AAII_BULLISH"].value, histories["AAII_BEARISH"].value)
    if frame.empty:
        st.warning("No common bullish and bearish reported dates.")
        return
    latest = frame.iloc[-1]
    a, b, c = st.columns(3)
    a.metric("Bullish − bearish", f"{latest.spread_pp:+.1f} pp")
    b.metric("Historical percentile", f"{latest.percentile:.0f}")
    c.metric("Current decile", f"{latest.decile:.0f} / 10")
    st.caption(
        f"AAII Reported Date: {frame.index[-1]:%d %b %Y} · {len(frame):,} surveys since {frame.index[0]:%Y}"
    )
    figure = go.Figure(
        go.Scatter(x=frame.index, y=frame.spread_pp, name="AAII bull − bear", connectgaps=False)
    )
    figure.add_hline(
        y=latest.spread_pp, line_color="#73BDA7", line_dash="dash", annotation_text="Latest spread"
    )
    figure.update_layout(title="AAII bull − bear spread")
    figure.update_yaxes(title="Percentage points")
    research_chart(figure, theme)
    price_key = "AAII_SP500_WEEKLY_CLOSE"
    if price_key in histories:
        summary, detail = decile_returns(frame, histories[price_key].value)
        st.subheader("Subsequent S&P 500 price returns by sentiment decile")
        st.caption(
            "Public-data alternative to Bloomberg total returns: AAII-reported weekly S&P 500 closes, excluding dividends. Dates label the source's report; the exact underlying close time is not supplied. Endpoints use the first reported close on or after each 1/3/6/12-calendar-month target, within seven days. Only completed horizons enter averages."
        )
        shown = summary[[f"{m}M mean (%)" for m in [1, 3, 6, 12]]].copy()
        shown.insert(
            0,
            "Sentiment",
            ["Bearish" if d == 1 else "Bullish" if d == 10 else "" for d in shown.index],
        )
        styled = shown.style.format(
            {c: "{:+.2f}" for c in shown.select_dtypes("number")}, na_rep="—"
        )
        styled = styled.apply(
            lambda row: [
                "background-color: #DDF1E9; font-weight: 600"
                if row.name == int(latest.decile)
                else ""
                for _ in row
            ],
            axis=1,
        )
        st.dataframe(styled, width="stretch")
        with st.expander("Valid sample counts and share of positive returns"):
            financial_table(summary.reset_index(), theme)
        _download(detail, "aaii_spread_and_forward_price_returns")
        st.download_button(
            "Download decile statistics", summary.to_csv(), "aaii_decile_statistics.csv", "text/csv"
        )
    else:
        st.warning(
            "Weekly S&P 500 closes are unavailable; the forward-return table awaits valid prices."
        )
    st.caption(
        "Deciles follow the workbook: full-sample inclusive percentile (three-decimal truncation), rounded to an integer; 0–10 is decile 1, 11–20 is decile 2, and so on. The highlighted row is the latest survey's decile. Full-sample bins change as history expands; weekly forward windows overlap. These are descriptive comparisons, with no claim of a publication-aware trading signal."
    )


def _btc(histories, theme):
    required = {"COINBASE_BTC_SPOT", *STRATEGY_IDS}
    if not required.issubset(histories):
        missing = [BY_ID[key]["name"] for key in required if key not in histories]
        st.info("Coverage calculations await: " + ", ".join(sorted(missing)) + ".")
        return
    dates = {histories[key].index[-1] for key in STRATEGY_IDS}
    vintages = {histories[key].retrieved_at.iloc[-1] for key in STRATEGY_IDS}
    if len(dates) != 1 or len(vintages) != 1:
        st.warning(
            "Company fields do not share one source snapshot. Refresh is required before calculating coverage."
        )
        return
    values = {key: float(histories[key].value.iloc[-1]) for key in required}
    try:
        result = coverage_snapshot(
            values["STRATEGY_BTC_HOLDINGS"],
            values["COINBASE_BTC_SPOT"],
            values["STRATEGY_DEBT_USD"],
            values["STRATEGY_PREFERRED_USD"],
            values["STRATEGY_BTC_COST_USD"],
        )
    except ValueError as exc:
        st.error(f"Coverage validation failed: {exc}")
        return
    st.subheader("MSTR BTC holdings market value to debt coverage")
    a, b, c = st.columns(3)
    a.metric("BTC / debt + preferred coverage", f"{result['coverage_x']:.2f}×")
    b.metric("BTC price for 1:1 coverage", f"${result['breakeven_btc_price_usd']:,.0f}")
    c.metric("Change to 1:1 coverage price", f"{result['downside_pct']:+.1f}%")
    fields = [
        ("BTC position", result["holdings_btc"], "BTC"),
        ("BTC price", result["btc_price_usd"], "USD/BTC"),
        ("BTC market value", result["btc_market_value_usdm"], "USD millions"),
        ("Total debt + preferred", result["debt_preferred_usdm"], "USD millions"),
        ("Loan to value", result["ltv_pct"], "%"),
        ("BTC / debt + preferred coverage", result["coverage_x"], "×"),
        ("BTC price for 1:1 coverage", result["breakeven_btc_price_usd"], "USD/BTC"),
        ("Downside vs current price", result["downside_pct"], "%"),
        ("Cost basis", result["cost_basis_usd"], "USD/BTC"),
        ("Unrealized gain / loss", result["gain_loss_usdm"], "USD millions"),
    ]
    table = pd.DataFrame(fields, columns=["Metric", "Value", "Units"])
    styled = table.style.format({"Value": "{:,.2f}"}, na_rep="—")
    styled = styled.apply(
        lambda row: [
            "background-color: #DDF1E9; font-weight: 600"
            if row.Metric in {"BTC price for 1:1 coverage", "Downside vs current price"}
            else "font-weight: 600"
            if row.Metric == "BTC market value"
            else ""
            for _ in row
        ],
        axis=1,
    )
    st.dataframe(styled, hide_index=True, width="stretch", height=430, row_height=36)
    st.download_button(
        "Download BTC coverage table", table.to_csv(index=False), "btc_coverage.csv", "text/csv"
    )
    quote = histories["COINBASE_BTC_SPOT"].published_at.iloc[-1]
    snapshot = next(iter(dates))
    st.caption(
        f"Coinbase quote time (UTC): {quote}. Strategy published statistics as of {snapshot:%d %b %Y}. Source and retrieval times are recorded separately."
    )
    metadata = source_metadata(STRATEGY_IDS[0])
    if metadata:
        st.caption(
            f"Strategy Ledger reported date: {metadata.get('company_reported_date', 'Not supplied')}. Cost basis can predate a debt/preferred update when the reported BTC position is unchanged; component dates are shown below."
        )
        with st.expander("Strategy snapshot source dates"):
            st.json(metadata)
    st.caption(
        "Coverage includes total debt plus preferred notional. LTV = claims / BTC market value; coverage is its reciprocal. The 1:1 price is claims / BTC held. Gain/loss uses aggregate average acquisition cost. This simplified workbook calculation excludes cash, other assets, taxes, liquidation costs and security-specific conversion terms; it is not a liquidation or default estimate."
    )


@st.fragment(run_every="60s")
def render_workbook_section(title):
    """Visible pages recheck automatically; network retrieval obeys source cadence."""
    theme = Theme("Market", "#5B365E", "#F0E9F2", ("#5B365E", "#73BDA7", "#647B91", "#B79A69"))
    ids = PAGE_IDS[title]
    enqueue(ids)
    if st.button("Check for available updates", key="workbook_refresh_" + title):
        enqueue(ids)
    st.caption(
        "This view updates every minute while open. Quote retrieval is limited to once every five minutes; other sources are checked daily. Failed requests retry after one hour. Monthly, quarterly and weekly data retain their publication lag."
    )
    histories = {key: h for key in ids if not (h := history(key)).empty}
    statuses = _status_rows(ids, histories)
    if statuses.Status.str.contains("STALE|failed", case=False).any():
        st.warning(
            "Some saved inputs are stale or their refresh failed. Review the source status and dates below before using the calculations."
        )
    {"Margin Debt": _margin, "Bull vs Bear": _sentiment, "BTC": _btc}[title](histories, theme)
    with st.expander("Sources, freshness and validation status", expanded=not bool(histories)):
        financial_table(statuses, theme)
        st.caption(
            "Public source downloads are validated before saving. Related AAII and Strategy fields are committed together. On failure, prior valid observations are retained and the failure remains visible. Quote source times are provided where available; other release dates are not inferred from observation dates."
        )
        st.download_button(
            "Download source status",
            statuses.to_csv(index=False),
            title.lower().replace(" ", "_") + "_sources.csv",
            "text/csv",
        )
