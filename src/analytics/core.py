"""Pure analytics. Dates are observation dates, never assumed publication dates."""

from datetime import date as calendar_date
from datetime import timedelta

import numpy as np
import pandas as pd


def aligned_value(series, date, max_gap_days=7):
    s = series.dropna().sort_index()
    eligible = s.loc[s.index <= pd.Timestamp(date)]
    if eligible.empty or (pd.Timestamp(date) - eligible.index[-1]).days > max_gap_days:
        return np.nan
    return float(eligible.iloc[-1])


def period_changes(series, basis_points=False, max_gap_days=7):
    s = series.dropna().sort_index()
    if s.empty:
        return {}
    end = s.index[-1]
    targets = {"YTD": pd.Timestamp(calendar_date(end.year, 1, 1) - timedelta(days=1))}
    targets.update({f"{m}M": end - pd.DateOffset(months=m) for m in [1, 3, 6, 12]})
    result = {}
    for label, date in targets.items():
        base = aligned_value(s, date, max_gap_days)
        result[label] = (
            (s.iloc[-1] - base) * 100 if basis_points else percentage_return(base, s.iloc[-1])
        )
    return result


def percentage_return(start, end):
    return (end / start - 1) * 100 if start > 0 else np.nan


def log_returns(s):
    return np.log(s.where(s > 0) / s.shift().where(s.shift() > 0))


def moving_average(s, window):
    return s.rolling(window, min_periods=window).mean()


def range_distance(s, window=252):
    x = s.dropna().tail(window)
    return (
        {
            "from_high_pct": percentage_return(x.max(), x.iloc[-1]),
            "from_low_pct": percentage_return(x.min(), x.iloc[-1]),
        }
        if len(x)
        else {}
    )


def drawdown(s):
    return (s / s.cummax() - 1) * 100


def volatility(s, window=21, annual_periods=252):
    return s.pct_change(fill_method=None).rolling(window).std() * np.sqrt(annual_periods) * 100


def relative(a, b):
    frame = pd.concat([a, b], axis=1).dropna()
    return frame.iloc[:, 0] / frame.iloc[:, 1].replace(0, np.nan)


def correlation(a, b, window=63):
    frame = pd.concat([a, b], axis=1).dropna().pct_change(fill_method=None)
    return frame.iloc[:, 0].rolling(window).corr(frame.iloc[:, 1])


def percentile(history, value):
    x = pd.Series(history).dropna()
    return float((x <= value).mean() * 100) if len(x) else np.nan


def decile(history, value):
    p = percentile(history, value)
    return min(10, max(1, int(np.ceil(p / 10)))) if np.isfinite(p) else None


def sector_outperformance(sectors, benchmark):
    valid = pd.Series(sectors).dropna()
    n = int((valid > benchmark).sum())
    return n, n / len(valid) * 100 if len(valid) else np.nan


def justified_pe(cost_of_equity, growth, retention):
    if not 0 <= retention <= 1 or cost_of_equity <= growth or cost_of_equity < 0:
        raise ValueError("Require 0 <= retention <= 1 and cost of equity > growth")
    return (1 - retention) / (cost_of_equity - growth)


def earnings_spread(pe, treasury_percent):
    return 100 / pe - treasury_percent if pe > 0 else np.nan


def ratio(numerator, denominator):
    return numerator / denominator if denominator > 0 else np.nan


def forward_returns(prices, months, max_gap_days=7):
    prices = prices.dropna().sort_index()
    # First session ON/AFTER the horizon, with bounded tolerance. Never backfill past data.
    out = {}
    for date, price in prices.items():
        target = date + pd.DateOffset(months=months)
        future = prices.loc[prices.index >= target]
        out[date] = (
            percentage_return(price, future.iloc[0])
            if len(future) and (future.index[0] - target).days <= max_gap_days
            else np.nan
        )
    return pd.Series(out)


def conditional_summary(returns):
    x = pd.Series(returns).dropna()
    return {"n": len(x), "median": x.median(), "win_rate_pct": (x > 0).mean() * 100}


def historical_comparison(series, dates, max_gap_days=7):
    values = pd.Series([aligned_value(series, d, max_gap_days) for d in dates]).dropna()
    return {
        "n": len(values),
        "mean": values.mean(),
        "median": values.median(),
        "min": values.min(),
        "max": values.max(),
    }


def scenario(capex, ocf, capex_growth, ocf_growth, years=5):
    if min(capex, ocf) < 0 or min(capex_growth, ocf_growth) <= -1:
        raise ValueError("Invalid starting values or growth")
    t = np.arange(years + 1)
    c, o = capex * (1 + capex_growth) ** t, ocf * (1 + ocf_growth) ** t
    return pd.DataFrame(
        {
            "year": t,
            "capex": c,
            "operating_cash_flow": o,
            "free_cash_flow": o - c,
            "capex_ocf": np.divide(c, o, out=np.full_like(c, np.nan, dtype=float), where=o != 0),
        }
    )
