"""Workbook margin ratios with explicit period and dollar-unit alignment."""

import numpy as np
import pandas as pd


def _period_series(values, frequency):
    series = values.dropna().sort_index().astype(float).copy()
    if not np.isfinite(series).all() or (series <= 0).any():
        raise ValueError("Margin inputs must be finite and positive")
    series.index = pd.to_datetime(series.index).to_period(frequency)
    if series.index.duplicated().any():
        raise ValueError("More than one observation per source period")
    return series


def quarterly_ratio(margin_millions, denominator, *, denominator_unit, start="2000-01-01"):
    """Join quarter-end margin months to the SAME quarter; never carry forward.

    GDP is a nominal annualized flow in billions; equity market value is a stock
    in millions. Both ratios are shown as percentage points (2.4 means 2.4%).
    FRED labels quarterly observations at quarter start, converted here only.
    """
    if denominator_unit not in {"USD billions", "USD millions"}:
        raise ValueError("Explicit USD billions or USD millions denominator required")
    debt = _period_series(margin_millions, "M")
    debt = debt[debt.index.month.isin([3, 6, 9, 12])]
    debt.index = debt.index.asfreq("Q")
    denom = _period_series(denominator, "Q")
    frame = pd.concat([debt.rename("margin_usd_millions"), denom.rename("denominator")], axis=1)
    frame = frame.dropna()
    factor = 1000 if denominator_unit == "USD billions" else 1
    frame["ratio_pct"] = frame.margin_usd_millions / (frame.denominator * factor) * 100
    frame.index = frame.index.to_timestamp(how="end").normalize()
    frame = frame.loc[start:]
    frame["historical_mean_pct"] = frame.ratio_pct.mean()
    frame.index.name = "quarter_end"
    return frame


def peak_comparison(latest_margin_millions):
    """Sponsor's rounded historical reference points, not algorithmic cycle calls."""
    records = [
        (2000, 300.0, 136.0),
        (2007, 416.0, 200.0),
        (2018, 669.0, 479.0),
        (2021, 919.0, 607.0),
    ]
    frame = pd.DataFrame(records, columns=["Cycle", "Peak (USD bn)", "Trough (USD bn)"])
    frame["Peak vs prior peak (%)"] = (
        frame["Peak (USD bn)"] / frame["Peak (USD bn)"].shift() - 1
    ) * 100
    frame["Peak vs prior trough (%)"] = (
        frame["Peak (USD bn)"] / frame["Trough (USD bn)"].shift() - 1
    ) * 100
    comparison = frame.iloc[1:4]
    for label, method in [("Average", "mean"), ("Median", "median")]:
        frame.loc[len(frame)] = [
            label,
            np.nan,
            np.nan,
            getattr(comparison["Peak vs prior peak (%)"], method)(),
            getattr(comparison["Peak vs prior trough (%)"], method)(),
        ]
    current = float(latest_margin_millions) / 1000
    frame.loc[len(frame)] = [
        "Current",
        current,
        np.nan,
        (current / 919 - 1) * 100,
        (current / 607 - 1) * 100,
    ]
    return frame
