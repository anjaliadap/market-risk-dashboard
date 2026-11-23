"""Pure analytics for the Housing, Banks, Valuation and Consumer pages.

Conventions follow ``src.analytics.core``: observation dates are not publication dates,
missing values are never forward-filled across unbounded gaps, and lagged comparisons use
the last observation on/before the calendar target within an explicit tolerance.
"""

import numpy as np
import pandas as pd

# Maximum distance between a calendar target and the observation used for it.
GAP_TOLERANCE_DAYS = {"daily": 7, "weekly": 10, "monthly": 20, "quarterly": 45, "annual": 400}


# Maximum age of the observation representing a calendar date (one full period). Quarterly FRED
# observations are dated at quarter start, so 2019-12-31 maps to the 2019-10-01 observation.
PERIOD_TOLERANCE_DAYS = {"daily": 7, "weekly": 10, "monthly": 35, "quarterly": 95, "annual": 370}


def tolerance(frequency):
    return GAP_TOLERANCE_DAYS.get(frequency, 20)


def period_tolerance(frequency):
    return PERIOD_TOLERANCE_DAYS.get(frequency, 35)


def ordinal(n):
    n = int(np.rint(n))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def lagged(series, months, max_gap_days):
    """Value observed ``months`` calendar months before each date (bounded as-of lookup)."""
    s = series.dropna().sort_index()
    if s.empty:
        return pd.Series(dtype=float)
    targets = pd.DataFrame({"target": s.index - pd.DateOffset(months=months)}, index=s.index)
    base = pd.DataFrame({"base_date": s.index, "base": s.to_numpy()})
    merged = pd.merge_asof(
        targets.sort_values("target"),
        base,
        left_on="target",
        right_on="base_date",
        direction="backward",
    )
    merged.index = targets.sort_values("target").index
    gap = (merged["target"] - merged["base_date"]).dt.days
    return merged["base"].where(gap <= max_gap_days).reindex(s.index)


def yoy_percent(series, max_gap_days=20, months=12):
    """Percent change versus the bounded observation ``months`` earlier."""
    s = series.dropna().sort_index()
    base = lagged(s, months, max_gap_days)
    return ((s / base.where(base > 0)) - 1) * 100


def yoy_change(series, max_gap_days=20, months=12):
    """Level change versus ``months`` earlier, in the series' own units (pp for rates)."""
    s = series.dropna().sort_index()
    return s - lagged(s, months, max_gap_days)


def prior_change(series):
    """Change from the immediately preceding observation."""
    s = series.dropna().sort_index()
    return float(s.iloc[-1] - s.iloc[-2]) if len(s) >= 2 else np.nan


def value_at(series, date, max_gap_days):
    s = series.dropna().sort_index()
    eligible = s.loc[s.index <= pd.Timestamp(date)]
    if eligible.empty or (pd.Timestamp(date) - eligible.index[-1]).days > max_gap_days:
        return np.nan
    return float(eligible.iloc[-1])


def history_percentile(series, start=None):
    """Empirical percentile (<=) of the latest value within its own history."""
    s = series.dropna()
    if start is not None:
        s = s.loc[pd.Timestamp(start) :]
    return float((s <= s.iloc[-1]).mean() * 100) if len(s) else np.nan


def zscore(series):
    s = series.dropna()
    if len(s) < 3 or s.std(ddof=1) == 0:
        return np.nan
    return float((s.iloc[-1] - s.mean()) / s.std(ddof=1))


def align_asof(left, right, max_gap_days):
    """Pair each ``left`` observation with the latest ``right`` value within tolerance."""
    a = left.dropna().sort_index()
    b = right.dropna().sort_index()
    if a.empty or b.empty:
        return pd.DataFrame(columns=["left", "right"])
    merged = pd.merge_asof(
        pd.DataFrame({"date": a.index, "left": a.to_numpy()}),
        pd.DataFrame({"right_date": b.index, "right": b.to_numpy()}),
        left_on="date",
        right_on="right_date",
        direction="backward",
    )
    merged = merged.loc[(merged["date"] - merged["right_date"]).dt.days <= max_gap_days]
    return merged.set_index("date")[["left", "right"]]


def mortgage_payment(principal, annual_rate_percent, years=30):
    """Level monthly principal-and-interest payment. Excludes taxes, insurance and PMI."""
    if principal < 0 or years <= 0:
        raise ValueError("Require non-negative principal and positive term")
    n = years * 12
    r = annual_rate_percent / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def payment_series(prices, rates_percent, down_payment=0.20, years=30, max_gap_days=10):
    """Monthly P&I on each price observation at the latest rate within tolerance."""
    pairs = align_asof(prices, rates_percent, max_gap_days)
    principal = pairs["left"] * (1 - down_payment)
    r = pairs["right"] / 100 / 12
    n = years * 12
    factor = np.where(r == 0, 1 / n, r / (1 - (1 + r) ** -n))
    return pd.Series(principal.to_numpy() * factor, index=pairs.index)


def payment_to_income(monthly_payment, annual_income, max_gap_days=730):
    """Annualized payment as a percent of annual income; income may be a lagged annual series."""
    pairs = align_asof(monthly_payment, annual_income, max_gap_days)
    return pairs["left"] * 12 / pairs["right"].where(pairs["right"] > 0) * 100


def scaled_ratio(numerator, denominator, scale=1.0, max_gap_days=45):
    """numerator × scale / denominator on as-of aligned dates (scale aligns units)."""
    pairs = align_asof(numerator, denominator, max_gap_days)
    return pairs["left"] * scale / pairs["right"].where(pairs["right"] != 0)


def real_growth(nominal_yoy, inflation_yoy, max_gap_days=20):
    """Approximate real growth: nominal Y/Y percent minus inflation Y/Y percent."""
    pairs = align_asof(nominal_yoy, inflation_yoy, max_gap_days)
    return pairs["left"] - pairs["right"]


def earnings_yield(pe):
    return 100 / pe if pe and pe > 0 else np.nan


def implied_growth(pe, cost_of_equity_percent, payout_ratio):
    """Perpetual growth (percent) implied by P/E = payout / (r − g)."""
    if not pe or pe <= 0 or not 0 <= payout_ratio <= 1:
        return np.nan
    return cost_of_equity_percent - payout_ratio / pe * 100


def pe_for_premium(real_yield_percent, premium_percent):
    """P/E consistent with earnings yield = real yield + premium (both percent)."""
    total = real_yield_percent + premium_percent
    return 100 / total if total > 0 else np.nan


def justified_pe_grid(costs_percent, growths_percent, retention):
    """Matrix of (1 − retention)/(r − g); undefined cells where r <= g."""
    payout = 1 - retention
    grid = {}
    for g in growths_percent:
        grid[g] = [payout / ((r - g) / 100) if r > g else np.nan for r in costs_percent]
    return pd.DataFrame(grid, index=costs_percent).T


def bands(series):
    """Full-sample mean and ±1 standard deviation for context lines."""
    s = series.dropna()
    if len(s) < 3:
        return {}
    mean, sd = float(s.mean()), float(s.std(ddof=1))
    return {"mean": mean, "upper": mean + sd, "lower": mean - sd}


def recession_spans(indicator):
    """(start, end) spans where a 0/1 recession indicator equals 1."""
    s = indicator.dropna().sort_index()
    spans, start = [], None
    for date, value in s.items():
        if value >= 1 and start is None:
            start = date
        elif value < 1 and start is not None:
            spans.append((start, date))
            start = None
    if start is not None:
        spans.append((start, s.index[-1]))
    return spans
