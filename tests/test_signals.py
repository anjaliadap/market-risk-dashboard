import numpy as np
import pandas as pd
import pytest

from src.analytics.signals import (
    Check,
    annualized_growth,
    apply_workbook_fallback,
    capex_coverage_check,
    checklist_as_of,
    days_since,
    funding_gap,
    implied_minus_realized,
    liquidity_check,
    output_gap,
    peak_status,
    period_cagr,
    productivity_check,
    ratio,
    recession_checklist,
    relative_strength_check,
    sales_vs_capex,
    sales_vs_capex_check,
    score,
    semiconductor_check,
    spread_vs_average_check,
    term_structure,
    vol_regime,
)


def monthly(values, start="2015-01-01"):
    return pd.Series(
        values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float
    )


def quarterly(values, start="2015-01-01"):
    return pd.Series(
        values, index=pd.date_range(start, periods=len(values), freq="QS"), dtype=float
    )


def daily(values, start="2024-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="B"), dtype=float)


def check(checks, metric):
    return next(c for c in checks if c.metric == metric)


def test_score_excludes_unavailable():
    checks = [Check("a", "", "", red=True), Check("b", "", "", red=False), Check("c", "", "")]
    assert score(checks) == (1, 2, 3)


def test_recession_checklist_rules():
    n = 40
    data = {
        # CPI accelerating: growth rate rises through the sample.
        "CPIAUCSL": monthly(100 * np.cumprod(1 + np.linspace(0.001, 0.004, n))),
        "DGS10": daily([4.0] * 10),
        "DGS2": daily([4.5] * 10),
        "UNRATE": monthly(np.linspace(3.5, 4.5, n)),
        "ICSA": monthly([500_000] * n),
        "INDPRO": monthly(np.linspace(110, 100, n)),
        "CES0500000003": monthly(30 * 1.003 ** np.arange(n)),
        "SP500": daily(np.linspace(5000, 6000, 400), "2023-01-02"),
    }
    checks = recession_checklist(data)
    assert len(checks) == 17
    assert check(checks, "Inflation").red is True
    assert check(checks, "Yield curve").red is True
    assert check(checks, "Yield curve").reading.startswith("-50 bp")
    assert check(checks, "Employment (Y/Y change)").red is True
    assert check(checks, "Initial jobless claims").status == "Above 475k"
    assert check(checks, "Industrial production (Y/Y)").red is True
    assert check(checks, "Wage growth").red is True  # 1.003^12 − 1 ≈ 3.66%
    assert check(checks, "Equity markets").red is False
    # Missing inputs and licensed items stay unavailable, never green.
    assert check(checks, "Output gap").red is None
    assert check(checks, "Composite PMI").red is None


def test_recession_threshold_boundaries():
    below = {
        "ICSA": monthly([475_000] * 3),
        "CES0500000003": monthly(100 * 1.0028 ** np.arange(30)),
    }
    checks = recession_checklist(below)
    assert check(checks, "Initial jobless claims").red is False  # strictly above 475k
    assert check(checks, "Wage growth").red is False  # 1.0028^12 − 1 ≈ 3.41%
    above = {"CES0500000003": monthly(100 * 1.0029 ** np.arange(30))}
    assert check(recession_checklist(above), "Wage growth").red is True  # ≈ 3.54%


def test_cyclical_components_majority_rule():
    data = {
        "DGORDER": monthly(100 * 1.002 ** np.arange(60)),  # steady growth = at its average
        "A007RL1Q225SBEA": quarterly([2.0] * 19 + [8.0]),
        "A011RL1Q225SBEA": quarterly([1.0] * 19 + [6.0]),
    }
    c = check(recession_checklist(data), "Cyclical components of GDP")
    assert c.red is True
    assert c.status.endswith("2 above average")


def test_output_gap_peaking():
    actual = quarterly([100, 102, 103, 102.5])
    potential = quarterly([100, 100, 100, 100])
    assert output_gap(actual, potential).round(2).tolist() == [0.0, 2.0, 3.0, 2.5]
    c = check(recession_checklist({"GDPC1": actual, "GDPPOT": potential}), "Output gap")
    assert c.red is True and c.status == "Peaking"


def test_credit_spread_widening_uses_three_month_change():
    spreads = daily(np.r_[np.full(80, 3.0), np.linspace(3.0, 3.8, 20)])
    c = check(recession_checklist({"BAMLH0A0HYM2": spreads}), "Credit spread")
    assert c.red is True
    assert "+80 bp" in c.reading


def test_workbook_fallback_only_fills_unavailable():
    checks = [Check("Composite PMI", "<47", "x"), Check("Inflation", "", "", red=False)]
    apply_workbook_fallback(
        checks, {"Composite PMI": ("Below 47", True), "Inflation": ("Accelerating", True)}
    )
    assert checks[0].red is True and checks[0].source.startswith("Workbook")
    assert checks[1].red is False  # independent result is never overwritten


def test_checklist_as_of_truncates_history():
    unemployment = monthly(np.r_[np.full(24, 4.0), np.full(24, 6.0)])
    before = check(
        checklist_as_of({"UNRATE": unemployment}, "2016-12-31"), "Employment (Y/Y change)"
    )
    after = check(
        checklist_as_of({"UNRATE": unemployment}, "2017-06-30"), "Employment (Y/Y change)"
    )
    assert before.red is False and after.red is True


def test_volatility_helpers():
    assert [vol_regime(x) for x in (12, 15, 25, 30, np.nan)] == [
        "Calm",
        "Normal",
        "Elevated",
        "Stress",
        "UNAVAILABLE",
    ]
    vix, vix3m = daily([20, 30]), daily([25, 25])
    assert term_structure(vix, vix3m).tolist() == [0.8, 1.2]
    assert days_since(daily([35, 20, 20, 20]), 30) == 3  # Business days span a calendar gap
    assert days_since(daily([10, 12]), 30) is None
    flat_prices = daily(np.full(40, 100.0))
    premium = implied_minus_realized(daily(np.full(40, 15.0)), flat_prices)
    assert premium.iloc[-1] == pytest.approx(15.0)


def test_growth_helpers():
    s = quarterly(100 * 1.02 ** (np.arange(21) / 4))  # 2% per year
    assert annualized_growth(s, 2).iloc[-1] == pytest.approx(2.0, abs=1e-6)
    assert period_cagr(s, "2015-01-01", "2020-01-01") == pytest.approx(2.0, abs=0.05)
    assert np.isnan(period_cagr(s, "2019-12-31", "2020-01-01"))
    status = peak_status(monthly([1, 3, 5, 4, 2]))
    assert status["observations_since_peak"] == 2 and status["drawdown"] == -3
    assert ratio(monthly([10, 20]), monthly([5, 5]), scale=100).tolist() == [200.0, 400.0]


def test_productivity_and_semiconductor_checks():
    slowing = quarterly(100 * np.cumprod(np.r_[1, np.full(8, 1.008), np.full(4, 1.004)]))
    c = productivity_check(slowing)
    assert c.red is True and c.status in {"Slowing", "Stalling"}
    output = monthly(100 * np.cumprod(np.r_[1, np.full(23, 1.01), np.full(12, 1.001)]))
    assert semiconductor_check(output).red is True
    assert productivity_check(quarterly([100, 101])).red is None


def test_sales_vs_capex_rules():
    rev = quarterly([0.20, 0.15])
    capex = quarterly([0.30, 0.40])
    signal = sales_vs_capex(rev, capex)
    assert signal["red"] is True
    accelerating = sales_vs_capex(quarterly([0.10, 0.25]), capex)
    assert accelerating["red"] is False
    assert sales_vs_capex(quarterly([0.1]), capex) is None
    c = sales_vs_capex_check({"A": signal, "B": accelerating, "C": signal})
    assert c.red is True and c.status == "2 of 3 companies flagged"
    assert sales_vs_capex_check({"A": None}).red is None


def test_financing_checks():
    assert capex_coverage_check(quarterly([0.9, 1.05])).red is True
    assert capex_coverage_check(quarterly([0.9, 0.95])).red is False
    workbook = spread_vs_average_check(monthly([5.0]), monthly([4.0]), "wb")
    assert workbook.red is True and workbook.source == "wb"
    proxy = spread_vs_average_check(
        pd.Series(dtype=float), pd.Series(dtype=float), "wb", daily([2.0, 2.0, 1.0])
    )
    assert proxy.red is False and proxy.source.startswith("FRED proxy")
    rs = relative_strength_check({"X": monthly([1.0, 1, 1, 0.9]), "Y": monthly([1.0, 1, 1, 0.8])})
    assert rs.red is True
    mixed = relative_strength_check(
        {"X": monthly([1.0, 1, 1, 1.1]), "Y": monthly([1.0, 1, 1, 0.8])}
    )
    assert mixed.red is False
    weeks = pd.date_range("2024-01-05", periods=60, freq="W-FRI")
    loose = pd.Series(np.linspace(-0.5, -0.45, 60), index=weeks)
    tight = pd.Series(np.linspace(-0.5, 0.0, 60), index=weeks)
    standards = quarterly([5.0])
    assert liquidity_check(loose, standards).red is False  # below the 0.25 SD threshold
    assert liquidity_check(tight, standards).red is True


def test_funding_gap_matches_quarters():
    gap = funding_gap(quarterly([10, 12, 15]), quarterly([11, 11, 11]))
    assert gap.tolist() == [-1, 1, 4]
