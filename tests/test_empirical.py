import numpy as np
import pandas as pd
import pytest

from src.analytics.empirical import (
    crossings,
    deviation,
    episodes,
    forward_return,
    history_stats,
    overweight,
    position_risk,
    reversion_levels,
    rolling_mean,
    signal_study,
)


def monthly(values, start="2000-01-31"):
    return pd.Series(
        values, index=pd.date_range(start, periods=len(values), freq="ME"), dtype=float
    )


def test_episodes_and_crossings():
    s = monthly([60, 72, 75, 65, 50, 71, 80])
    runs = episodes(s, 70)
    assert [(r["months"], r["peak"], r["ongoing"]) for r in runs] == [(2, 75, False), (2, 80, True)]
    assert runs[0]["start"] == s.index[1].date() and runs[0]["end"] == s.index[2].date()
    assert crossings(s, 70) == [s.index[1], s.index[5]]
    assert episodes(monthly([10, 20]), 70) == []
    # A series that starts above the threshold counts as a crossing at its first observation.
    assert crossings(monthly([75, 60]), 70) == [monthly([75, 60]).index[0]]


def test_forward_return_bounded():
    prices = monthly([100, 110, 121, 133.1])
    assert forward_return(prices, prices.index[0], 2) == pytest.approx(21.0)
    assert np.isnan(forward_return(prices, prices.index[2], 6))  # beyond the saved history
    # Two missing months: the nearest earlier price is ~60 days old, beyond the 35-day tolerance.
    gappy = prices.drop(prices.index[1:3])
    assert np.isnan(forward_return(gappy, prices.index[0], 2))


def test_signal_study_compares_with_all_months():
    signal = monthly([50, 75, 50, 50, 75, 50, 50, 50, 50, 50])
    prices = monthly(100 * 1.01 ** np.arange(10))
    events, summary = signal_study(signal, prices, 70, horizons=(3,))
    assert len(events) == 2
    row = summary.iloc[0]
    assert row["Crossings with data"] == 2
    assert row["After crossings: mean (%)"] == pytest.approx((1.01**3 - 1) * 100)
    assert row["All months: share positive (%)"] == 100


def test_history_stats_match_sponsor_definitions():
    s = monthly([0.10, 0.20, 0.30, 0.40, 0.20, 0.10, 0.30, 0.20, 0.10, 0.20, 0.30, 0.20, 0.25])
    stats = history_stats(s)
    assert stats["mean"] == pytest.approx(s.mean())
    assert stats["std"] == pytest.approx(s.std(ddof=1))  # Excel STDEV is the sample estimate
    assert stats["from_mean"] == pytest.approx((0.25 - s.mean()) / s.std(ddof=1))
    assert stats["chg_1m"] == pytest.approx(0.05)
    assert stats["chg_12m"] == pytest.approx(0.15)
    assert history_stats(monthly([0.1])) is None


def test_portfolio_rules():
    assert overweight(0.10, 0.05) == "Overweight"
    assert overweight(0.05, 0.05) == "Underweight"  # strictly greater, as in the sponsor formula
    assert overweight(None, 0.05) is None
    assert position_risk("Overweight", 0.5) == "Risk"
    assert position_risk("Overweight", -0.1) == "Less Risk"
    assert position_risk("Underweight", 2.0) is None
    assert position_risk("Overweight", np.nan) is None


def test_ratio_reversion_and_deviation():
    levels = reversion_levels(6000.0, 3000.0, 2.5)
    assert levels["implied_index"] == pytest.approx(7500)
    assert levels["index_change"] == pytest.approx(25)
    assert levels["implied_asset"] == pytest.approx(2400)
    assert levels["asset_change"] == pytest.approx(-20)
    assert reversion_levels(6000.0, 0.0, 2.5) is None
    assert deviation(monthly([2.2, 1.8]), monthly([2.0, 2.0])).round(6).tolist() == [10.0, -10.0]
    assert rolling_mean(monthly(np.arange(90)), 84).dropna().iloc[0] == pytest.approx(41.5)
