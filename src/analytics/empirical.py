"""Pure analytics for the Momentum, FC Data, Failure Candidates and S&P Relative pages.

Inputs are the sponsor's saved monthly series. Nothing here fills gaps or extends history:
lagged and forward lookups use the last observation on/before a calendar target within a
bounded tolerance, and comparisons that would need missing data return NaN / None.
"""

import numpy as np
import pandas as pd

from src.analytics.sectors import value_at

MONTH_GAP = 35  # Monthly observations may sit anywhere in the month (e.g., a mid-month last row).


def clean(series):
    if series is None:
        return pd.Series(dtype=float)
    return series.dropna().sort_index().astype(float)


# --- Thresholds and episodes ---------------------------------------------------------------------


def episodes(series, threshold):
    """Contiguous runs at/above ``threshold``: start, end, peak, peak date, months, ongoing."""
    s = clean(series)
    above = s >= threshold
    out, start = [], None
    for i, (date, flag) in enumerate(above.items()):
        if flag and start is None:
            start = i
        if start is not None and (not flag or i == len(s) - 1):
            stop = i if flag else i - 1
            run = s.iloc[start : stop + 1]
            out.append(
                {
                    "start": run.index[0].date(),
                    "end": run.index[-1].date(),
                    "months": len(run),
                    "peak": float(run.max()),
                    "peak_date": run.idxmax().date(),
                    "ongoing": bool(flag and i == len(s) - 1),
                }
            )
            start = None
    return out


def crossings(series, threshold):
    """Dates where the series moves from below to at/above ``threshold``."""
    s = clean(series)
    above = s >= threshold
    return list(s.index[above & ~above.shift(1, fill_value=False)])


def forward_return(prices, date, months, max_gap_days=MONTH_GAP):
    """Price return (%) from ``date`` to ``months`` later; NaN if either end is unavailable."""
    p = clean(prices)
    if p.empty:
        return np.nan
    start = pd.Timestamp(date)
    # Month-end dates stay on month ends (Feb 29 + 3 months is May 31, not May 29).
    step = pd.offsets.MonthEnd(months) if start.is_month_end else pd.DateOffset(months=months)
    target = start + step
    if target > p.index[-1] + pd.Timedelta(days=max_gap_days):
        return np.nan
    base = value_at(p, date, max_gap_days)
    end = value_at(p, target, max_gap_days)
    if np.isnan(base) or np.isnan(end) or base <= 0:
        return np.nan
    return (end / base - 1) * 100


def signal_study(signal, prices, threshold, horizons=(3, 6, 12)):
    """Forward price returns after each upward threshold crossing versus all months.

    Returns (events frame, summary frame). Events overlap with each other when crossings are
    close together, and the sample is small, so this is descriptive, not a tested strategy.
    """
    events = []
    for date in crossings(signal, threshold):
        row = {"Crossing": date.date(), "Score": float(clean(signal).loc[date])}
        row.update({f"S&P {h}M (%)": forward_return(prices, date, h) for h in horizons})
        events.append(row)
    events = pd.DataFrame(events)
    summary = []
    s = clean(signal)
    for h in horizons:
        after = events[f"S&P {h}M (%)"].dropna() if len(events) else pd.Series(dtype=float)
        every = pd.Series([forward_return(prices, d, h) for d in s.index]).dropna()
        summary.append(
            {
                "Horizon": f"{h}M",
                "After crossings: mean (%)": after.mean() if len(after) else np.nan,
                "After crossings: share positive (%)": (after > 0).mean() * 100
                if len(after)
                else np.nan,
                "Crossings with data": len(after),
                "All months: mean (%)": every.mean() if len(every) else np.nan,
                "All months: share positive (%)": (every > 0).mean() * 100
                if len(every)
                else np.nan,
            }
        )
    return events, pd.DataFrame(summary)


def change_over(series, observations):
    """Latest value minus the value ``observations`` rows earlier (NaN if too short)."""
    s = clean(series)
    return float(s.iloc[-1] - s.iloc[-1 - observations]) if len(s) > observations else np.nan


# --- Failure-candidate statistics ----------------------------------------------------------------


def history_stats(series):
    """Recompute the sponsor's FC Data statistics from the saved monthly history.

    Matches FC Data!UV:VE definitions: max, min, mean, sample standard deviation, (latest −
    mean) / std, and trailing changes over 1/3/6/12 observations.
    """
    s = clean(series)
    if len(s) < 2:
        return None
    mean, sd = float(s.mean()), float(s.std(ddof=1))
    return {
        "latest": float(s.iloc[-1]),
        "as_of": s.index[-1].date(),
        "max": float(s.max()),
        "min": float(s.min()),
        "mean": mean,
        "std": sd,
        "from_mean": (float(s.iloc[-1]) - mean) / sd if sd > 0 else np.nan,
        "percentile": float((s <= s.iloc[-1]).mean() * 100),
        **{f"chg_{n}m": change_over(s, n) for n in (1, 3, 6, 12)},
    }


def overweight(portfolio_weight, benchmark_weight):
    """Sponsor rule (Failure Candidates!AO:AP): Overweight if portfolio weight > S&P weight."""
    if portfolio_weight is None or benchmark_weight is None:
        return None
    return "Overweight" if portfolio_weight > benchmark_weight else "Underweight"


def position_risk(relative, from_mean):
    """Sponsor rule (AR:AS): 'Risk' if overweight and failure share above its mean."""
    if relative != "Overweight" or from_mean is None or np.isnan(from_mean):
        return None
    return "Risk" if from_mean > 0 else "Less Risk"


# --- S&P relative to gold and oil ----------------------------------------------------------------


def deviation(ratio, average):
    """Percent deviation of a ratio from its moving average on common dates."""
    pair = pd.concat([clean(ratio), clean(average)], axis=1, keys=["r", "a"]).dropna()
    return (pair["r"] / pair["a"].where(pair["a"] > 0) - 1) * 100


def reversion_levels(index_level, asset_price, ratio_average):
    """Implied levels if the ratio returned to its moving average, holding the other leg fixed.

    Returns the implied S&P 500 (asset price held) and implied asset price (S&P held), with the
    percent change versus current levels. Mirrors the sponsor's Gold to Oil implied-price block.
    """
    if not all(np.isfinite(v) and v > 0 for v in (index_level, asset_price, ratio_average)):
        return None
    implied_index = ratio_average * asset_price
    implied_asset = index_level / ratio_average
    return {
        "implied_index": implied_index,
        "index_change": (implied_index / index_level - 1) * 100,
        "implied_asset": implied_asset,
        "asset_change": (implied_asset / asset_price - 1) * 100,
    }


def rolling_mean(series, months=84):
    """Trailing mean over ``months`` monthly observations (the sponsor uses 7 years = 84)."""
    s = clean(series)
    return s.rolling(months, min_periods=months).mean()
