"""Financial acceptance examples, independent of the source workbook cache."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.margin_debt import peak_comparison, quarterly_ratio
from src.analytics.sentiment import decile_returns, forward_price_returns, spread_history


def dated(values, dates):
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


def test_gdp_ratio_aligns_fred_quarter_start_and_trading_month_end_in_dollar_units():
    debt = dated([500_000, 1_500_000], ["2024-03-28", "2024-06-28"])
    gdp = dated([25_000, 30_000], ["2024-01-01", "2024-04-01"])
    result = quarterly_ratio(debt, gdp, denominator_unit="USD billions")
    assert result.index.tolist() == [pd.Timestamp("2024-03-31"), pd.Timestamp("2024-06-30")]
    assert result.ratio_pct.tolist() == pytest.approx([2, 5])
    # Arithmetic mean of the two observed ratios, not a ratio of summed inputs.
    assert result.historical_mean_pct.tolist() == pytest.approx([3.5, 3.5])
    assert result.margin_usd_millions.tolist() == [500_000, 1_500_000]


def test_market_value_in_millions_has_no_gdp_thousand_conversion():
    debt = dated([600_000], ["2024-03-29"])
    capitalization = dated([30_000_000], ["2024-01-01"])
    result = quarterly_ratio(debt, capitalization, denominator_unit="USD millions")
    assert result.ratio_pct.iloc[0] == pytest.approx(2)
    with pytest.raises(ValueError, match="Explicit"):
        quarterly_ratio(debt, capitalization, denominator_unit="index points")


def test_missing_quarter_end_debt_and_denominator_are_never_filled():
    debt = dated([500_000, 550_000, 650_000], ["2024-03-29", "2024-05-31", "2024-09-30"])
    gdp = dated([25_000, 30_000], ["2024-01-01", "2024-04-01"])
    result = quarterly_ratio(debt, gdp, denominator_unit="USD billions")
    # Q2 lacks June debt, even though May is available; Q3 lacks its own GDP.
    assert result.index.tolist() == [pd.Timestamp("2024-03-31")]
    assert result.ratio_pct.iloc[0] == pytest.approx(2)


def test_next_quarter_extends_ratio_history_and_recalculates_full_history_mean():
    debt = dated([500_000, 1_500_000], ["2024-03-31", "2024-06-30"])
    gdp = dated([25_000, 30_000], ["2024-01-01", "2024-04-01"])
    before = quarterly_ratio(debt, gdp, denominator_unit="USD billions")
    debt.loc[pd.Timestamp("2024-09-30")] = 3_000_000
    gdp.loc[pd.Timestamp("2024-07-01")] = 30_000
    after = quarterly_ratio(debt, gdp, denominator_unit="USD billions")
    assert len(after) == len(before) + 1
    assert after.index[-1] == pd.Timestamp("2024-09-30")
    assert after.ratio_pct.iloc[-1] == pytest.approx(10)
    assert after.historical_mean_pct.tolist() == pytest.approx([17 / 3] * 3)


def test_ratio_rejects_duplicate_reference_period_and_nonpositive_inputs():
    gdp = dated([25_000], ["2024-01-01"])
    duplicate_debt = dated([500_000, 600_000], ["2024-03-28", "2024-03-29"])
    with pytest.raises(ValueError, match="source period"):
        quarterly_ratio(duplicate_debt, gdp, denominator_unit="USD billions")
    for bad in [0, -1, np.inf]:
        with pytest.raises(ValueError, match="finite and positive"):
            quarterly_ratio(
                dated([500_000], ["2024-03-29"]),
                dated([bad], ["2024-01-01"]),
                denominator_unit="USD billions",
            )


def test_current_peak_row_converts_finra_millions_to_billions():
    result = peak_comparison(1_400_000)
    current = result.iloc[-1]
    assert current["Cycle"] == "Current"
    assert current["Peak (USD bn)"] == 1400
    assert current["Peak vs prior peak (%)"] == pytest.approx((1400 / 919 - 1) * 100)
    assert current["Peak vs prior trough (%)"] == pytest.approx((1400 / 607 - 1) * 100)
    assert result.iloc[1]["Peak vs prior trough (%)"] == pytest.approx((416 / 136 - 1) * 100)


def test_spread_is_bull_minus_bear_and_excel_ties_use_first_rank():
    dates = pd.date_range("2024-01-04", periods=6, freq="7D")
    bulls = pd.Series([40, 50, 50, 60, 70, 80], index=dates)
    bears = pd.Series([50] * 6, index=dates)
    result = spread_history(bulls, bears)
    assert result.spread_pp.tolist() == [-10, 0, 0, 10, 20, 30]
    assert result.percentile.tolist() == [0, 20, 20, 60, 80, 100]
    assert result.decile.tolist() == [1, 2, 2, 6, 8, 10]


def test_excel_half_up_rounding_and_decile_boundaries():
    dates = pd.date_range("2024-01-04", periods=9, freq="7D")
    half_up = spread_history(pd.Series(range(40, 49), index=dates), pd.Series(40, index=dates))
    # Rank 1/(9-1) is 12.5%; Excel ROUND rounds this to 13, not banker's 12.
    assert half_up.percentile.iloc[1] == 13
    dates = pd.date_range("2024-01-04", periods=11, freq="7D")
    result = spread_history(pd.Series(range(40, 51), index=dates), pd.Series(40, index=dates))
    assert result.percentile.tolist() == list(range(0, 101, 10))
    assert result.decile.tolist() == [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def test_sentiment_extension_recomputes_descriptive_ranks_and_joins_by_date():
    bulls = dated([40, 50, 60], ["2024-01-04", "2024-01-11", "2024-01-18"])
    bears = dated([50, 50, 50], ["2024-01-04", "2024-01-11", "2024-01-18"])
    before = spread_history(bulls, bears)
    bulls.loc[pd.Timestamp("2024-01-25")] = 70
    # A missing bear must not borrow the previous row's bearish reading.
    missing = spread_history(bulls, bears)
    assert missing.index.tolist() == before.index.tolist()
    bears.loc[pd.Timestamp("2024-01-25")] = 50
    after = spread_history(bulls, bears)
    assert len(after) == 4
    assert before.percentile.iloc[-1] == 100
    assert after.percentile.iloc[2] == 67
    assert after.percentile.iloc[-1] == 100


def test_forward_return_uses_calendar_month_and_first_close_on_or_after_target():
    prices = dated([100, 90, 110], ["2024-01-31", "2024-02-28", "2024-03-01"])
    result = forward_price_returns([pd.Timestamp("2024-01-31")], prices, 1)
    # Jan 31 + one calendar month = Feb 29; Feb 28's earlier close is ineligible.
    assert result.iloc[0] == pytest.approx(10)


def test_unmatured_forward_returns_stay_missing_until_next_source_row_arrives():
    date = pd.Timestamp("2024-01-04")
    prices = dated([100, 109], ["2024-01-04", "2024-02-01"])
    assert pd.isna(forward_price_returns([date], prices, 1).iloc[0])
    prices.loc[pd.Timestamp("2024-02-08")] = 110
    assert forward_price_returns([date], prices, 1).iloc[0] == pytest.approx(10)


def test_forward_returns_bound_missing_session_gap_and_never_use_a_prior_close():
    date = pd.Timestamp("2024-01-04")
    within = dated([100, 110], ["2024-01-11", "2024-02-11"])
    outside = dated([100, 110], ["2024-01-12", "2024-02-12"])
    assert forward_price_returns([date], within, 1).iloc[0] == pytest.approx(10)
    assert pd.isna(forward_price_returns([date], outside, 1).iloc[0])


def test_decile_table_counts_only_observed_matured_horizons_and_positive_returns():
    dates = pd.to_datetime(["2024-01-04", "2024-02-04", "2024-03-04"])
    spreads = pd.DataFrame({"decile": [1, 1, 10]}, index=dates)
    prices = pd.Series([100, 110, 99], index=dates)
    summary, details = decile_returns(spreads, prices)
    assert summary.index.tolist() == list(range(1, 11))
    assert details["1M"].iloc[:2].tolist() == pytest.approx([10, -10])
    assert summary.loc[1, "1M n"] == 2
    assert summary.loc[1, "1M mean (%)"] == pytest.approx(0)
    assert summary.loc[1, "1M higher (%)"] == 50
    assert summary.loc[10, "1M n"] == 0
    assert pd.isna(summary.loc[10, "1M mean (%)"])
    assert summary["3M n"].sum() == 0
    assert details[["3M", "6M", "12M"]].isna().all().all()


def test_price_return_validation_rejects_duplicate_or_invalid_index_levels():
    dates = pd.to_datetime(["2024-01-04", "2024-02-04"])
    for values in [[100, 0], [100, -1], [100, np.inf]]:
        with pytest.raises(ValueError, match="finite positive"):
            forward_price_returns(dates[:1], pd.Series(values, index=dates), 1)
    with pytest.raises(ValueError, match="unique dates"):
        forward_price_returns(dates[:1], pd.Series([100, 101], index=[dates[0]] * 2), 1)


@pytest.mark.parametrize("ascending_rank", [1176, 1177])
def test_excel_percentile_575_rounds_to_58_despite_binary_float_ties(ascending_rank):
    # The supplied workbook has both ranks among 2,045 observations. Both
    # PERCENTRANK results truncate to .575, whose Excel integer percentile is 58.
    # Calculating floor(.575 * 100 + .5) with binary floats incorrectly gives 57.
    dates = pd.date_range("1987-07-23", periods=2045, freq="7D")
    bulls = pd.Series(np.linspace(0, 100, len(dates)), index=dates)
    bears = pd.Series(50.0, index=dates)
    result = spread_history(bulls, bears)
    assert result.percentile.iloc[ascending_rank] == 58
    assert result.decile.iloc[ascending_rank] == 6


def test_workbook_cached_margin_and_btc_formula_reconciliation():
    from src.analytics.btc import coverage_snapshot

    # Constants are source-workbook formula controls, never a live-data fallback.
    debt = dated([1_502_072], ["2026-06-30"])
    gdp = dated([32_563.03], ["2026-04-01"])
    margin = quarterly_ratio(debt, gdp, denominator_unit="USD billions")
    assert margin.ratio_pct.iloc[0] == pytest.approx(4.61281397953446)

    btc = coverage_snapshot(846_000, 80_833.48, 6_714_000_000, 14_294_000_000, 75_416)
    assert btc["btc_market_value_usdm"] == pytest.approx(68_385.12408)
    assert btc["debt_preferred_usdm"] == 21_008
    assert btc["ltv_pct"] == pytest.approx(30.72013143593027)
    assert btc["coverage_x"] == pytest.approx(3.255194405940594)
    assert btc["breakeven_btc_price_usd"] == pytest.approx(24_832.151300236408)
    assert btc["downside_pct"] == pytest.approx(-69.27986856406973)
    assert btc["gain_loss_usdm"] == pytest.approx(4_583.18808)


def test_peak_average_and_median_summarize_only_historical_comparison_columns():
    result = peak_comparison(1_400_000).set_index("Cycle")
    prior_peak = [(416 / 300 - 1) * 100, (669 / 416 - 1) * 100, (919 / 669 - 1) * 100]
    prior_trough = [(416 / 136 - 1) * 100, (669 / 200 - 1) * 100, (919 / 479 - 1) * 100]
    assert result.loc["Average", "Peak vs prior peak (%)"] == pytest.approx(np.mean(prior_peak))
    assert result.loc["Median", "Peak vs prior peak (%)"] == pytest.approx(np.median(prior_peak))
    assert result.loc["Average", "Peak vs prior trough (%)"] == pytest.approx(np.mean(prior_trough))
    assert result.loc["Median", "Peak vs prior trough (%)"] == pytest.approx(
        np.median(prior_trough)
    )
    assert (
        result.loc[["Average", "Median"], ["Peak (USD bn)", "Trough (USD bn)"]].isna().all().all()
    )
    assert result.index[-1] == "Current"
