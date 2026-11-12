"""Descriptive AAII spread deciles and matured price-return comparisons."""

import numpy as np
import pandas as pd


def spread_history(bulls, bears):
    frame = pd.concat([bulls.rename("bullish_pct"), bears.rename("bearish_pct")], axis=1)
    frame = frame.dropna().sort_index()
    if frame.empty:
        return frame.assign(spread_pp=np.nan, percentile=np.nan, decile=np.nan)
    if frame.index.duplicated().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Duplicate dates or non-finite sentiment")
    if ((frame < 0) | (frame > 100)).any().any():
        raise ValueError("Sentiment must be expressed in percent, 0 to 100")
    frame["spread_pp"] = frame.bullish_pct - frame.bearish_pct
    # Excel PERCENTRANK.INC uses the first tied rank and truncates to .001.
    # ROUND(...*100,0) uses half-up for nonnegative percentages, unlike np.rint.
    n = len(frame)
    ranks = (
        (frame.spread_pp.rank(method="min") - 1) / (n - 1)
        if n > 1
        else pd.Series(0.0, index=frame.index)
    )
    thousandths = np.floor(np.round(ranks * 1000, 9)).astype(int)
    frame["percentile"] = (thousandths + 5) // 10
    frame["decile"] = np.ceil(frame.percentile / 10).clip(1, 10).astype(int)
    return frame


def forward_price_returns(survey_dates, prices, months, *, max_gap_days=7):
    """First available close on/after reported date and calendar-month horizon.

    Thursday survey dates come from AAII's Reported Date field. No assumed
    intraday release time or publication-aware tradable strategy is claimed.
    A horizon must have fully elapsed; incomplete trailing observations are NaN.
    """
    p = prices.dropna().sort_index().astype(float)
    if p.index.duplicated().any() or not np.isfinite(p).all() or (p <= 0).any():
        raise ValueError("Prices must have unique dates and finite positive levels")
    result = pd.Series(np.nan, index=pd.DatetimeIndex(survey_dates), dtype=float)
    for date in result.index:
        target = date + pd.DateOffset(months=months)
        base = p.loc[p.index >= date]
        end = p.loc[p.index >= target]
        if base.empty or end.empty:
            continue
        if (base.index[0] - date).days > max_gap_days or (
            end.index[0] - target
        ).days > max_gap_days:
            continue
        result.loc[date] = (end.iloc[0] / base.iloc[0] - 1) * 100
    return result


def decile_returns(spreads, prices):
    """Full-sample descriptive bins; overlapping weekly horizons, not a backtest."""
    details = spreads.copy()
    summary = pd.DataFrame(index=pd.Index(range(1, 11), name="Decile"))
    for months in [1, 3, 6, 12]:
        label = f"{months}M"
        details[label] = forward_price_returns(details.index, prices, months)
        grouped = details.groupby("decile")[label]
        summary[f"{label} mean (%)"] = grouped.mean()
        summary[f"{label} n"] = grouped.count().reindex(summary.index, fill_value=0)
        summary[f"{label} higher (%)"] = grouped.apply(lambda x: (x.dropna() > 0).mean() * 100)
    return summary, details
