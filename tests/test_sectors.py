import numpy as np
import pandas as pd
import pytest

from src.analytics.sectors import (
    align_asof,
    bands,
    earnings_yield,
    history_percentile,
    implied_growth,
    justified_pe_grid,
    lagged,
    mortgage_payment,
    payment_series,
    payment_to_income,
    pe_for_premium,
    prior_change,
    real_growth,
    recession_spans,
    scaled_ratio,
    value_at,
    yoy_change,
    yoy_percent,
    zscore,
)


def monthly(values, start="2020-01-31"):
    return pd.Series(
        values, index=pd.date_range(start, periods=len(values), freq="ME"), dtype=float
    )


def test_yoy_uses_bounded_lag():
    s = monthly(np.arange(100, 125))
    out = yoy_percent(s)
    assert np.isnan(out.iloc[11])
    assert out.iloc[12] == pytest.approx((112 / 100 - 1) * 100)
    assert yoy_change(s).iloc[-1] == pytest.approx(12)
    # A gap larger than tolerance leaves the comparison unavailable instead of reaching back.
    gapped = s.drop(s.index[0:3])
    assert np.isnan(yoy_percent(gapped, max_gap_days=20).loc[s.index[13]])


def test_lagged_month_end_alignment():
    s = monthly([1.0] * 12 + [2.0])
    assert lagged(s, 12, 20).iloc[-1] == 1.0


def test_quarterly_yoy_and_prior():
    q = pd.Series(
        [1.0, 1.5, 2.0, 2.5, 3.0], index=pd.date_range("2020-01-01", periods=5, freq="QS")
    )
    assert yoy_change(q, 45).iloc[-1] == pytest.approx(2.0)
    assert prior_change(q) == pytest.approx(0.5)
    assert np.isnan(prior_change(q.iloc[:1]))


def test_mortgage_payment_matches_annuity_formula():
    assert mortgage_payment(300_000, 6.0) == pytest.approx(1798.65, abs=0.01)
    assert mortgage_payment(120_000, 0, 10) == pytest.approx(1000)
    with pytest.raises(ValueError):
        mortgage_payment(-1, 5)


def test_payment_and_burden_series():
    prices = pd.Series([375_000.0], index=pd.to_datetime(["2024-01-01"]))
    rates = pd.Series([6.0, 7.0], index=pd.to_datetime(["2023-12-28", "2024-01-04"]))
    payment = payment_series(prices, rates, down_payment=0.2)
    assert payment.iloc[0] == pytest.approx(mortgage_payment(300_000, 6.0))
    income = pd.Series([100_000.0], index=pd.to_datetime(["2023-01-01"]))
    burden = payment_to_income(payment, income)
    assert burden.iloc[0] == pytest.approx(payment.iloc[0] * 12 / 100_000 * 100)
    # Stale beyond tolerance: unavailable rather than carried forward.
    assert payment_to_income(payment, income, max_gap_days=30).empty


def test_ratio_alignment_and_units():
    equities = pd.Series([50_000_000.0], index=pd.to_datetime(["2024-01-01"]))  # millions
    gdp = pd.Series([25_000.0], index=pd.to_datetime(["2024-01-01"]))  # billions
    assert scaled_ratio(equities, gdp, 0.1).iloc[0] == pytest.approx(200)
    assert scaled_ratio(equities, gdp * 0).isna().all()
    assert align_asof(pd.Series(dtype=float), gdp, 5).empty


def test_valuation_helpers():
    assert earnings_yield(20) == 5
    assert np.isnan(earnings_yield(0))
    assert implied_growth(20, 9, 0.4) == pytest.approx(7)
    assert np.isnan(implied_growth(20, 9, 1.5))
    assert pe_for_premium(2, 3) == 20
    assert np.isnan(pe_for_premium(-4, 3))
    grid = justified_pe_grid([8, 10], [4, 9], 0.5)
    assert grid.loc[4, 10] == pytest.approx(0.5 / 0.06)
    assert np.isnan(grid.loc[9, 8])


def test_distribution_helpers():
    s = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.date_range("2001-01-01", periods=4, freq="YS"))
    assert history_percentile(s) == 100
    assert history_percentile(s, "2003-01-01") == 100
    assert zscore(s) == pytest.approx((4 - 2.5) / s.std())
    assert np.isnan(zscore(s.iloc[:2]))
    assert bands(s)["mean"] == 2.5
    assert value_at(s, "2002-06-01", 400) == 2
    assert np.isnan(value_at(s, "2002-06-01", 30))


def test_real_growth_and_recessions():
    a = monthly([5.0, 6.0])
    b = monthly([2.0, 4.0])
    assert list(real_growth(a, b)) == [3.0, 2.0]
    usrec = monthly([0, 1, 1, 0, 1])
    spans = recession_spans(usrec)
    assert spans[0] == (usrec.index[1], usrec.index[3])
    assert spans[1] == (usrec.index[4], usrec.index[4])


def test_quarter_start_baseline_and_ordinal():
    from src.analytics.sectors import ordinal, period_tolerance

    q = pd.Series([2.0, 3.0], index=pd.to_datetime(["2019-10-01", "2020-01-01"]))
    assert value_at(q, "2019-12-31", period_tolerance("quarterly")) == 2.0
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 22, 99.6)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "22nd",
        "100th",
    ]
