"""Banks: credit quality, lending standards, balance-sheet growth and funding."""

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.sections.common import (
    PRE_PANDEMIC,
    Kpi,
    chart_or_note,
    clip,
    cross_check,
    derived_metric,
    kpi_row,
    line_figure,
    load,
    lookback_start,
    page_tabs,
    refresh_controls,
    render_workbook,
    snapshot_table,
    sources_table,
    yoy,
)
from src.analytics.sectors import (
    history_percentile,
    period_tolerance,
    prior_change,
    scaled_ratio,
    tolerance,
    value_at,
    yoy_change,
    zscore,
)
from src.registry import BY_ID

DELINQUENCY = {
    "All loans": "DRALACBS",
    "Credit card": "DRCCLACBS",
    "CRE ex-farmland": "DRCRELEXFACBS",
    "Business (C&I)": "DRBLACBS",
    "Residential mortgage": "DRSFRMACBS",
}
CHARGE_OFFS = {"All loans": "CORALACBS", "Credit card": "CORCCACBS", "Business (C&I)": "CORBLACBS"}
STANDARDS = {"C&I (large/middle firms)": "DRTSCILM", "Credit card": "DRTSCLCC"}
IDS = [
    *DELINQUENCY.values(),
    *CHARGE_OFFS.values(),
    *STANDARDS.values(),
    "TOTLL",
    "DPSACBW027SBOG",
    "USREC",
]
KPIS = [
    Kpi("DRALACBS", "Delinq. · all loans", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("CORALACBS", "NCOs · all loans", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("DRCCLACBS", "Delinq. · cards", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("DRCRELEXFACBS", "Delinq. · CRE", "{:.2f}%", "yoy_pp", inverse=True),
    Kpi("TOTLL", "Loans & leases", "${:,.0f}bn", "yoy_pct"),
    Kpi("DPSACBW027SBOG", "Deposits", "${:,.0f}bn", "yoy_pct"),
]
TABLE = [
    *[(k, "pp") for k in DELINQUENCY.values()],
    *[(k, "pp") for k in CHARGE_OFFS.values()],
    *[(k, "pp") for k in STANDARDS.values()],
    ("TOTLL", "pct"),
    ("DPSACBW027SBOG", "pct"),
]
CROSS_CHECKS = [("banks_0_0", "NCOs (BISPRBAC, sponsor population)", "CORALACBS")]
NOTES = [
    (
        "Delinquency and charge-off rates are Federal Reserve quarterly, seasonally adjusted, all "
        "insured U.S.-chartered commercial banks. Charge-offs are annualized and net of recoveries."
    ),
    (
        "The sponsor workbook's NCO series (BISPRBAC Index, NET_CHARGE_OFF_RATE_AVG) covers the "
        "Bloomberg bank-index population; it is shown separately and never replaced by the Fed universe."
    ),
    (
        "SLOOS values are net percentages of senior loan officers reporting tighter minus easier "
        "standards; positive means tightening. Survey dates are quarter starts."
    ),
    (
        "Loans (TOTLL) and deposits are H.8 weekly, seasonally adjusted, billions USD. Loan-to-deposit "
        "is an aggregate balance-sheet ratio, not a regulatory liquidity measure."
    ),
    (
        "Credit stress table: percentile and z-score against retained history (requested since 2000), "
        "which includes the 2009–2010 peak; a low percentile is not evidence of low future losses."
    ),
    (
        "FDIC Quarterly Banking Profile items (NIM, reserves, unrealized securities losses) are not "
        "connected; FRED's FFIEC NIM/ROA series were discontinued and are intentionally excluded."
    ),
]


def render(ctx, render_section):
    data = load(IDS)
    workbook_tab, analytics_tab, indicators_tab, method_tab = page_tabs(ctx.title)
    with workbook_tab:
        render_workbook(ctx.title, render_section)
    with analytics_tab:
        refresh_controls(ctx, IDS)
        kpi_row(data, KPIS)
        start = lookback_start("banks", default="20Y")
        _credit_quality(ctx, data, start)
        _standards_and_balance_sheet(ctx, data, start)
    with indicators_tab:
        snapshot_table(ctx, data, TABLE, "banks_indicators.csv")
        with st.expander("Workbook vs independent source cross-check"):
            cross_check(ctx, data, ctx.title, CROSS_CHECKS, "banks_xc")
    with method_tab:
        sources_table(ctx, IDS, NOTES)


def stress_table(data):
    rows = []
    for family, mapping in (("Delinquency", DELINQUENCY), ("Net charge-off", CHARGE_OFFS)):
        for label, key in mapping.items():
            s = data.get(key, pd.Series(dtype=float)).dropna()
            if s.empty:
                rows.append({"Measure": f"{family} · {label}", "Status": "UNAVAILABLE"})
                continue
            gap = tolerance(BY_ID[key]["frequency"])
            pre = value_at(s, PRE_PANDEMIC, period_tolerance(BY_ID[key]["frequency"]))
            rows.append(
                {
                    "Measure": f"{family} · {label}",
                    "Latest (%)": s.iloc[-1],
                    "Quarter": s.index[-1].to_period("Q").strftime("%YQ%q"),
                    "Q/Q (pp)": prior_change(s),
                    "Y/Y (pp)": yoy_change(s, gap).iloc[-1],
                    "vs 2019-Q4 (pp)": s.iloc[-1] - pre if np.isfinite(pre) else np.nan,
                    "Peak since 2000 (%)": s.loc["2000":].max(),
                    "Percentile since 2000": history_percentile(s, "2000-01-01"),
                    "Z-score": zscore(s.loc["2000":]),
                    "Status": "AVAILABLE / DELAYED",
                }
            )
    return pd.DataFrame(rows)


def _credit_quality(ctx, data, start):
    st.subheader("Credit quality")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        series = {label: clip(data.get(key, empty), start) for label, key in DELINQUENCY.items()}
        chart_or_note(
            ctx,
            line_figure("Delinquency rates by loan type (%, SA)", series, left_title="Percent"),
            [series],
            "banks_delinquency",
            "Delinquency rates not ingested.",
            data,
            start,
        )
    with right:
        series = {label: clip(data.get(key, empty), start) for label, key in CHARGE_OFFS.items()}
        chart_or_note(
            ctx,
            line_figure("Net charge-off rates (%, annualized, SA)", series, left_title="Percent"),
            [series],
            "banks_chargeoffs",
            "Charge-off rates not ingested.",
            data,
            start,
        )
    st.markdown("**Credit stress monitor**")
    table = stress_table(data)
    ctx.table_view(table, hide_index=True)
    st.caption(
        "Q/Q and Y/Y are percentage-point changes. 2019-Q4 is the pre-pandemic baseline. "
        "Percentile/z-score are descriptive ranks over retained history, not forecasts."
    )


def _standards_and_balance_sheet(ctx, data, start):
    st.subheader("Lending standards, loan growth & funding")
    empty = pd.Series(dtype=float)
    left, right = st.columns(2)
    with left:
        series = {label: clip(data.get(key, empty), start) for label, key in STANDARDS.items()}
        chart_or_note(
            ctx,
            line_figure(
                "SLOOS · net % of banks tightening standards",
                series,
                left_title="Net percent",
                zero=True,
            ),
            [series],
            "banks_sloos",
            "SLOOS series not ingested.",
            data,
            start,
        )
    with right:
        growth = {
            "Loans & leases Y/Y": clip(yoy(data, "TOTLL"), start),
            "Deposits Y/Y": clip(yoy(data, "DPSACBW027SBOG"), start),
        }
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Loan and deposit growth (% Y/Y)", growth, left_title="Percent", zero=True
            ),
            [growth],
            "banks_growth",
            "H.8 loans/deposits not ingested.",
            data,
            start,
        )
    ldr = (
        scaled_ratio(data["TOTLL"], data["DPSACBW027SBOG"], 100, 7)
        if {"TOTLL", "DPSACBW027SBOG"} <= data.keys()
        else empty
    )
    a, b = st.columns([1, 3])
    gap = tolerance("weekly")
    change = yoy_change(ldr, gap).iloc[-1] if not ldr.empty else np.nan
    derived_metric(
        a,
        "Loan-to-deposit ratio",
        ldr,
        "{:.1f}%",
        "H.8 aggregate",
        None if pd.isna(change) else f"{change:+.1f} pp Y/Y",
    )
    with b:
        chart_or_note(
            ctx,
            line_figure(
                "DERIVED · Loan-to-deposit ratio (%)",
                {"Loans / deposits": clip(ldr, start)},
                left_title="Percent",
            ),
            [{"l": ldr}],
            "banks_ldr",
            "Requires TOTLL and deposits.",
            data,
            start,
        )
