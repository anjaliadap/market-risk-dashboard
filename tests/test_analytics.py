import numpy as np
import pandas as pd
import pytest

from src.analytics.core import (
    aligned_value,
    conditional_summary,
    decile,
    drawdown,
    earnings_spread,
    forward_returns,
    justified_pe,
    moving_average,
    percentage_return,
    percentile,
    period_changes,
    range_distance,
    ratio,
    scenario,
    sector_outperformance,
)


def test_returns_and_bp():
    assert percentage_return(100, 110) == pytest.approx(10)
    assert np.isnan(percentage_return(0, 10))
    s = pd.Series([4.0, 4.25], index=pd.to_datetime(["2023-12-29", "2024-01-31"]))
    assert period_changes(s, True)["YTD"] == 25
    assert np.isnan(aligned_value(s, "2024-03-01"))


def test_moving_range_breadth():
    s = pd.Series([80.0, 100.0, 120.0, 90.0])
    assert moving_average(s, 2).iloc[-1] == 105
    assert range_distance(s)["from_high_pct"] == -25
    assert range_distance(s)["from_low_pct"] == 12.5
    assert sector_outperformance([2, 4, 6], 3) == (2, pytest.approx(200 / 3))
    assert drawdown(s).iloc[-1] == -25


def test_financial_ratios():
    assert justified_pe(0.10, 0.05, 0.5) == 10
    with pytest.raises(ValueError):
        justified_pe(0.05, 0.05, 0.5)
    assert earnings_spread(20, 4) == 1
    assert ratio(100, 200) == 0.5
    assert ratio(500, 25000) * 100 == 2
    assert np.isnan(ratio(1, 0))


def test_forward_and_distribution():
    s = pd.Series([100, 110, 99], index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]))
    f = forward_returns(s, 1)
    assert f.iloc[0] == pytest.approx(10)
    assert f.iloc[1] == pytest.approx(-10)
    assert np.isnan(f.iloc[2])
    assert conditional_summary(f)["win_rate_pct"] == 50
    assert percentile([1, 2, 3, 4], 2) == 50
    assert decile([1, 2, 3, 4], 2) == 5
    assert decile([1, 2], 100) == 10


def test_scenario():
    result = scenario(100, 200, 0.1, 0.05, 1)
    assert result.capex.iloc[-1] == pytest.approx(110)
    assert result.free_cash_flow.iloc[-1] == pytest.approx(100)
