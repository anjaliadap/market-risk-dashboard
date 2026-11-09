"""Rule-based monitors for the Recession, VIX & Options, Demand, Financing and Supply pages.

Every rule is explicit, deterministic and documented next to its check. A check whose inputs are
missing is UNAVAILABLE (``red is None``) and is excluded from the evaluated count; it is never
assumed green. Conventions follow ``src.analytics.sectors``: lagged comparisons use the last
observation on/before the calendar target within a bounded tolerance, and observation dates are
not publication dates.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from src.analytics.sectors import align_asof, lagged, yoy_change, yoy_percent

LONG_RUN_START = "2000-01-01"
NFCI_TIGHTENING = 0.25  # NFCI is scaled to mean 0, standard deviation 1
GAP = {"daily": 7, "weekly": 10, "monthly": 20, "quarterly": 45}
VIX_REGIMES = ((15, "Calm"), (20, "Normal"), (30, "Elevated"), (np.inf, "Stress"))


@dataclass
class Check:
    metric: str
    warning_reading: str
    rule: str
    reading: str = "—"
    status: str = "UNAVAILABLE"
    red: bool | None = None
    as_of: object = None
    source: str = ""

    def __setattr__(self, name, value):
        # Rules compare numpy scalars; store plain Python booleans for export and equality.
        if name == "red" and value is not None:
            value = bool(value)
        super().__setattr__(name, value)

    def row(self):
        out = asdict(self)
        out["signal"] = "UNAVAILABLE" if self.red is None else "RED" if self.red else "Not red"
        return out


# --- Small helpers -------------------------------------------------------------------------------


def clean(series):
    if series is None:
        return pd.Series(dtype=float)
    return series.dropna().sort_index().astype(float)


def last(series):
    s = clean(series)
    return (float(s.iloc[-1]), s.index[-1].date()) if len(s) else (np.nan, None)


def nth_last(series, n):
    """Value ``n`` observations before the latest (n=0 is the latest)."""
    s = clean(series)
    return float(s.iloc[-1 - n]) if len(s) > n else np.nan


def long_run_mean(series, start=LONG_RUN_START):
    s = clean(series).loc[pd.Timestamp(start) :]
    return float(s.mean()) if len(s) else np.nan


def change_over(series, months, max_gap_days):
    """Latest value minus the bounded observation ``months`` calendar months earlier."""
    s = clean(series)
    if s.empty:
        return np.nan
    base = lagged(s, months, max_gap_days).iloc[-1]
    return float(s.iloc[-1] - base) if pd.notna(base) else np.nan


def score(checks):
    """(red count, evaluated count, total count)."""
    evaluated = [c for c in checks if c.red is not None]
    return sum(bool(c.red) for c in evaluated), len(evaluated), len(checks)


def _ready(check, value, as_of, source):
    check.as_of, check.source = as_of, source
    return not (value is None or (isinstance(value, float) and np.isnan(value)))


# --- Recession checklist -------------------------------------------------------------------------

# Sponsor workbook row for each item (Recession!B:G); used for side-by-side comparison/fallback.
RECESSION_ROWS = {
    "Inflation": 8,
    "Yield curve": 10,
    "Inventory/sales ratio": 13,
    "Cyclical components of GDP": 16,
    "Employment (Y/Y change)": 20,
    "Initial jobless claims": 23,
    "Leading economic indicators (Y/Y)": 26,
    "Industrial production (Y/Y)": 29,
    "Personal income (Y/Y)": 32,
    "Output gap": 35,
    "Real money supply (Y/Y)": 37,
    "Wage growth": 40,
    "Composite PMI": 43,
    "10Yr less GDP growth": 45,
    "Credit spread": 47,
    "Consumer confidence": 49,
    "Equity markets": 52,
}
LICENSED = "Licensed source not connected (Conference Board / S&P Global / ISM)"


def recession_checklist(data):
    """Independent 17-item recession checklist mirroring the sponsor's Recession tab."""
    d = {k: clean(v) for k, v in data.items()}
    get = lambda key: d.get(key, pd.Series(dtype=float))
    checks = []

    # 1. Inflation: CPI-U Y/Y now vs three monthly observations earlier.
    c = Check("Inflation", "Accelerating", "CPI-U Y/Y above its level 3 months earlier")
    cpi = yoy_percent(get("CPIAUCSL"), GAP["monthly"]).dropna()
    now, as_of = last(cpi)
    prior = nth_last(cpi, 3)
    if _ready(c, prior, as_of, "FRED: CPIAUCSL") and not np.isnan(now):
        c.red = now > prior
        c.status = "Accelerating" if c.red else "Decelerating / stable"
        c.reading = f"{now:.1f}% Y/Y (3M earlier {prior:.1f}%)"
    checks.append(c)

    # 2. Yield curve: 10Y − 2Y on common observation dates.
    c = Check("Yield curve", "Inverted", "10Y − 2Y Treasury spread below 0 bp")
    pair = pd.concat([get("DGS10"), get("DGS2")], axis=1, keys=["y10", "y2"]).dropna()
    if len(pair):
        bp = (pair["y10"].iloc[-1] - pair["y2"].iloc[-1]) * 100
        _ready(c, bp, pair.index[-1].date(), "FRED: DGS10 − DGS2")
        c.red = bp < 0
        c.status = "Inverted" if c.red else "Not inverted"
        extra = ""
        t3m, _ = last(get("T10Y3M"))
        if not np.isnan(t3m):
            extra = f"; 10Y − 3M {t3m * 100:+.0f} bp"
        c.reading = f"{bp:+.0f} bp{extra}"
    checks.append(c)

    # 3. Inventory/sales: above its long-run average AND rising Y/Y.
    c = Check(
        "Inventory/sales ratio",
        "Above average excess",
        "Retail inventories/sales above its average since 2000 and higher than a year earlier",
    )
    ratio = get("RETAILIRSA")
    now, as_of = last(ratio)
    average = long_run_mean(ratio)
    change = change_over(ratio, 12, GAP["monthly"])
    if _ready(c, change, as_of, "FRED: RETAILIRSA") and not np.isnan(average):
        above = now > average
        c.red = bool(above and change > 0)
        c.status = ("Above average" if above else "Below average") + (
            ", rising Y/Y" if change > 0 else ", falling Y/Y"
        )
        c.reading = f"{now:.2f} (avg {average:.2f}; {change:+.2f} Y/Y)"
    checks.append(c)

    # 4. Cyclical components: durables orders Y/Y, real fixed and residential investment growth.
    c = Check(
        "Cyclical components of GDP",
        "Significantly above LT average",
        "At least 2 of 3 (durable goods orders Y/Y, real fixed investment, real residential "
        "investment growth) above their averages since 2000",
    )
    components = {
        "Durable goods orders Y/Y": yoy_percent(get("DGORDER"), GAP["monthly"]),
        "Fixed investment": get("A007RL1Q225SBEA"),
        "Residential investment": get("A011RL1Q225SBEA"),
    }
    readings, above, dates = [], 0, []
    for label, series in components.items():
        now, as_of = last(series)
        average = long_run_mean(series)
        if np.isnan(now) or np.isnan(average):
            readings = None
            break
        above += now > average
        dates.append(as_of)
        readings.append(f"{label} {now:+.1f}% (avg {average:+.1f}%)")
    if readings is not None:
        _ready(c, 0.0, min(dates), "FRED: DGORDER, A007RL1Q225SBEA, A011RL1Q225SBEA")
        c.red = above >= 2
        c.status = f"{3 - above} below average, {above} above average"
        c.reading = "; ".join(readings)
    checks.append(c)

    # 5. Employment: unemployment rate higher than a year earlier.
    c = Check("Employment (Y/Y change)", "Declining", "Unemployment rate higher than 12 months ago")
    change = yoy_change(get("UNRATE"), GAP["monthly"]).dropna()
    now, as_of = last(change)
    if _ready(c, now, as_of, "FRED: UNRATE"):
        c.red = now > 0
        c.status = "Declining" if c.red else "Advancing"
        c.reading = f"Unemployment {last(get('UNRATE'))[0]:.1f}% ({now:+.1f} pp Y/Y)"
    checks.append(c)

    # 6. Initial claims: weekly level above 475k (650k marks severe stress in the sponsor sheet).
    c = Check("Initial jobless claims", "475k / 650k", "Weekly initial claims above 475k")
    now, as_of = last(get("ICSA"))
    if _ready(c, now, as_of, "FRED: ICSA"):
        thousands = now / 1000
        c.red = thousands > 475
        c.status = "Above 650k" if thousands > 650 else "Above 475k" if c.red else "Below 475k"
        average, _ = last(get("IC4WSA"))
        c.reading = f"{thousands:,.0f}k" + (
            f" (4-wk avg {average / 1000:,.0f}k)" if not np.isnan(average) else ""
        )
    checks.append(c)

    # 7. Leading indicators: Conference Board LEI is licensed; no free substitute is claimed.
    checks.append(Check("Leading economic indicators (Y/Y)", "Declining", LICENSED))

    # 8. Industrial production Y/Y.
    checks.append(
        _yoy_sign_check(
            "Industrial production (Y/Y)", get("INDPRO"), "INDPRO", "Increasing", "Declining"
        )
    )

    # 9. Personal income: real, excluding transfers (the NBER dating measure).
    checks.append(
        _yoy_sign_check(
            "Personal income (Y/Y)",
            get("W875RX1"),
            "W875RX1 (real, ex-transfers)",
            "Increasing",
            "Declining",
        )
    )

    # 10. Output gap: positive but narrowing = peaking.
    c = Check(
        "Output gap",
        "Peaking",
        "Real GDP above CBO potential and the gap narrower than the prior quarter",
    )
    gap = output_gap(get("GDPC1"), get("GDPPOT"))
    now, as_of = last(gap)
    prior = nth_last(gap, 1)
    if _ready(c, prior, as_of, "FRED: GDPC1 vs GDPPOT") and not np.isnan(now):
        c.red = bool(now > 0 and now < prior)
        c.status = (
            "Peaking" if c.red else "Above potential, widening" if now > 0 else "Below potential"
        )
        c.reading = f"{now:+.2f}% of potential (prior quarter {prior:+.2f}%)"
    checks.append(c)

    # 11. Real money supply Y/Y.
    checks.append(
        _yoy_sign_check(
            "Real money supply (Y/Y)", get("M2REAL"), "M2REAL", "Increasing", "Declining"
        )
    )

    # 12. Wage growth above 3.5%.
    c = Check("Wage growth", ">3.5%", "Average hourly earnings (private) Y/Y above 3.5%")
    growth = yoy_percent(get("CES0500000003"), GAP["monthly"]).dropna()
    now, as_of = last(growth)
    if _ready(c, now, as_of, "FRED: CES0500000003"):
        c.red = now > 3.5
        c.status = "Above 3.5%" if c.red else "At or below 3.5%"
        c.reading = f"{now:.1f}% Y/Y"
    checks.append(c)

    # 13. Composite PMI is licensed.
    checks.append(Check("Composite PMI", "<47", LICENSED))

    # 14. 10Y yield less nominal GDP growth.
    c = Check(
        "10Yr less GDP growth", ">0", "10Y Treasury yield minus nominal GDP Y/Y growth above 0"
    )
    gdp = yoy_percent(get("GDP"), GAP["quarterly"]).dropna()
    growth, gdp_date = last(gdp)
    yield10, yield_date = last(get("DGS10"))
    if _ready(c, growth, gdp_date, "FRED: DGS10, GDP") and not np.isnan(yield10):
        diff = yield10 - growth
        c.as_of = yield_date
        c.red = diff > 0
        c.status = "Above 0" if c.red else "Below 0"
        c.reading = f"{diff:+.2f} pp (10Y {yield10:.2f}%; GDP {growth:.1f}% Y/Y to {gdp_date})"
    checks.append(c)

    # 15. Credit spreads: HY OAS widened by more than 50 bp over three months.
    c = Check("Credit spread", "Widening", "High-yield OAS more than 50 bp wider than 3 months ago")
    hy = get("BAMLH0A0HYM2")
    now, as_of = last(hy)
    change = change_over(hy, 3, GAP["daily"])
    if _ready(c, change, as_of, "FRED: BAMLH0A0HYM2"):
        c.red = change * 100 > 50
        c.status = (
            "Widening" if c.red else "Stable / tightening" if change <= 0 else "Drifting wider"
        )
        c.reading = f"{now * 100:.0f} bp ({change * 100:+.0f} bp over 3M)"
    checks.append(c)

    # 16. Consumer confidence: 12-month change in UMich sentiment.
    c = Check("Consumer confidence", "Declining", "UMich sentiment lower than 12 months ago")
    change = yoy_change(get("UMCSENT"), GAP["monthly"]).dropna()
    now, as_of = last(change)
    if _ready(c, now, as_of, "FRED: UMCSENT"):
        c.red = now < 0
        c.status = "Declining" if c.red else "Improving"
        c.reading = f"{last(get('UMCSENT'))[0]:.1f} ({now:+.1f} pts Y/Y)"
    checks.append(c)

    # 17. Equity market: S&P 500 12-month price change.
    checks.append(
        _yoy_sign_check(
            "Equity markets", get("SP500"), "SP500", "Advancing", "Declining", GAP["daily"]
        )
    )
    return checks


def _yoy_sign_check(metric, series, source, up, down, gap=GAP["monthly"]):
    c = Check(metric, down, f"Y/Y change below 0 ({source})")
    growth = yoy_percent(series, gap).dropna()
    now, as_of = last(growth)
    if _ready(c, now, as_of, "FRED: " + source):
        c.red = now < 0
        c.status = down if c.red else up
        c.reading = f"{now:+.1f}% Y/Y"
    return c


def checklist_as_of(data, when):
    """Checklist evaluated on observations dated on/before ``when`` (current-vintage data).

    Observation dates are not release dates and values are revised, so this shows how the rules
    read on revised data at a reference date, not what an analyst could have seen in real time.
    """
    cutoff = pd.Timestamp(when)
    return recession_checklist({k: clean(v).loc[:cutoff] for k, v in data.items()})


def apply_workbook_fallback(checks, saved):
    """Fill UNAVAILABLE checks from the sponsor's saved manual flags.

    ``saved`` maps metric -> (status text or None, flagged bool). Only checks without an
    independent source are filled; independent results are never overwritten.
    """
    for c in checks:
        if c.red is None and c.metric in saved:
            status, flagged = saved[c.metric]
            c.red = bool(flagged)
            c.status = status or ("Flagged" if flagged else "Not flagged")
            c.reading = "Sponsor saved status"
            c.source = "Workbook (saved manual flag)"
    return checks


def output_gap(real_gdp, potential):
    """Percent deviation of real GDP from potential on aligned quarterly dates."""
    pairs = align_asof(clean(real_gdp), clean(potential), GAP["quarterly"])
    if pairs.empty:
        return pd.Series(dtype=float)
    return (pairs["left"] / pairs["right"].where(pairs["right"] > 0) - 1) * 100


def sahm_rule(unemployment):
    """3-month average unemployment minus its minimum over the prior 12 months (current data)."""
    s = clean(unemployment)
    average = s.rolling(3, min_periods=3).mean()
    return average - average.rolling(12, min_periods=12).min()


# --- Volatility ----------------------------------------------------------------------------------


def vol_regime(level):
    if level is None or np.isnan(level):
        return "UNAVAILABLE"
    return next(label for bound, label in VIX_REGIMES if level < bound)


def realized_volatility(prices, window=21, periods=252):
    """Annualized close-to-close log-return volatility in percent."""
    s = clean(prices)
    returns = np.log(s.where(s > 0) / s.shift().where(s.shift() > 0))
    return returns.rolling(window, min_periods=window).std() * np.sqrt(periods) * 100


def term_structure(front, back):
    """Front / back implied volatility on common dates (>1 = inverted / backwardation)."""
    pair = pd.concat([clean(front), clean(back)], axis=1, keys=["front", "back"]).dropna()
    return pair["front"] / pair["back"].where(pair["back"] > 0)


def implied_minus_realized(implied, prices, window=21):
    """VIX minus trailing realized S&P 500 volatility (both annualized percent)."""
    realized = realized_volatility(prices, window)
    pair = pd.concat([clean(implied), realized], axis=1, keys=["iv", "rv"]).dropna()
    return pair["iv"] - pair["rv"]


def days_since(series, threshold):
    """Calendar days since the series last closed at/above ``threshold`` (None if never)."""
    s = clean(series)
    hits = s.loc[s >= threshold]
    if hits.empty:
        return None
    return int((s.index[-1] - hits.index[-1]).days)


def percentile_rank(series, value=None, start=None):
    s = clean(series)
    if start is not None:
        s = s.loc[pd.Timestamp(start) :]
    if s.empty:
        return np.nan
    value = s.iloc[-1] if value is None else value
    return float((s <= value).mean() * 100)


# --- Demand / supply / financing -----------------------------------------------------------------


def annualized_growth(series, years, max_gap_days=GAP["quarterly"]):
    """Compound annual growth versus the bounded observation ``years`` earlier (percent)."""
    s = clean(series)
    if s.empty:
        return pd.Series(dtype=float)
    base = lagged(s, int(12 * years), max_gap_days)
    return ((s / base.where(base > 0)) ** (1 / years) - 1) * 100


def period_cagr(series, start, end=None):
    """Compound annual growth between the observations nearest on/before ``start`` and ``end``."""
    s = clean(series)
    first = s.loc[: pd.Timestamp(start)]
    last_ = s.loc[: pd.Timestamp(end)] if end is not None else s
    if first.empty or last_.empty or first.iloc[-1] <= 0:
        return np.nan
    years = (last_.index[-1] - first.index[-1]).days / 365.25
    if years <= 0.5:
        return np.nan
    return float(((last_.iloc[-1] / first.iloc[-1]) ** (1 / years) - 1) * 100)


def ratio(numerator, denominator, max_gap_days=GAP["monthly"], scale=1.0):
    pairs = align_asof(clean(numerator), clean(denominator), max_gap_days)
    if pairs.empty:
        return pd.Series(dtype=float)
    return pairs["left"] * scale / pairs["right"].where(pairs["right"] != 0)


def momentum(series, smoothing=3):
    """Y/Y percent change smoothed with a trailing ``smoothing``-observation mean."""
    growth = yoy_percent(clean(series), GAP["monthly"])
    return growth.rolling(smoothing, min_periods=smoothing).mean()


def peak_status(series, lookback=24):
    """Where the latest value sits relative to the maximum of the trailing ``lookback`` points.

    Returns {peak, peak_date, observations_since_peak, latest, drawdown} or None. A growth series
    whose latest value is its trailing maximum is 'at peak'; otherwise it is past the peak by the
    reported number of observations. Descriptive only.
    """
    s = clean(series).tail(lookback)
    if len(s) < 3:
        return None
    peak_date = s.idxmax()
    return {
        "peak": float(s.max()),
        "peak_date": peak_date.date(),
        "observations_since_peak": int(len(s.loc[peak_date:]) - 1),
        "latest": float(s.iloc[-1]),
        "drawdown": float(s.iloc[-1] - s.max()),
    }


def productivity_check(productivity):
    c = Check(
        "Slowing or stalling productivity growth",
        "Slowing / stalling",
        "Nonfarm productivity Y/Y below 1% (stalling) or below its rate four quarters earlier "
        "(slowing)",
    )
    growth = yoy_percent(clean(productivity), GAP["quarterly"]).dropna()
    now, as_of = last(growth)
    prior = nth_last(growth, 4)
    if _ready(c, prior, as_of, "FRED: OPHNFB") and not np.isnan(now):
        stalling, slowing = now < 1.0, now < prior
        c.red = bool(stalling or slowing)
        c.status = "Stalling" if stalling else "Slowing" if slowing else "Accelerating"
        c.reading = f"{now:.1f}% Y/Y (4Q earlier {prior:.1f}%)"
    return c


def semiconductor_check(production, shipments=None):
    c = Check(
        "Declining semiconductor billings momentum",
        "Declining momentum",
        "3-month average Y/Y growth in semiconductor output (IP, NAICS 3344) below its level "
        "3 months earlier. Proxy: SIA/WSTS billings are licensed",
    )
    smoothed = momentum(production).dropna()
    now, as_of = last(smoothed)
    prior = nth_last(smoothed, 3)
    if _ready(c, prior, as_of, "FRED: IPG3344S (proxy)") and not np.isnan(now):
        c.red = now < prior
        c.status = "Declining momentum" if c.red else "Rising momentum"
        c.reading = f"{now:+.1f}% Y/Y 3MMA (3M earlier {prior:+.1f}%)"
        ship = momentum(shipments).dropna() if shipments is not None else pd.Series(dtype=float)
        if len(ship):
            c.reading += f"; computer & electronic shipments {ship.iloc[-1]:+.1f}%"
    return c


def sales_vs_capex(revenue_growth, capex_growth):
    """Per-company signal from reported TTM growth fractions.

    RED when capex (+R&D) growth exceeds revenue growth AND revenue growth slowed versus the
    prior reported quarter. Returns None when either series has fewer than two quarters.
    """
    rev, cap = clean(revenue_growth), clean(capex_growth)
    if len(rev) < 2 or cap.empty:
        return None
    latest, prior, capex = float(rev.iloc[-1]), float(rev.iloc[-2]), float(cap.iloc[-1])
    return {
        "revenue": latest,
        "revenue_prior": prior,
        "capex": capex,
        "as_of": rev.index[-1].date(),
        "red": bool(capex > latest and latest < prior),
    }


def sales_vs_capex_check(companies):
    """Majority rule across companies; ``companies`` maps name -> sales_vs_capex output."""
    c = Check(
        "Slowing AI sales growth vs capex growth",
        "Capex growth > slowing sales growth",
        "For a majority of hyperscalers: TTM capex+R&D growth above TTM sales growth, and sales "
        "growth below the prior reported quarter",
    )
    results = {k: v for k, v in companies.items() if v is not None}
    if not results:
        return c
    flagged = [k for k, v in results.items() if v["red"]]
    c.red = len(flagged) > len(results) / 2
    c.status = f"{len(flagged)} of {len(results)} companies flagged"
    c.reading = "; ".join(
        f"{k}: sales {v['revenue']:.0%} (prior {v['revenue_prior']:.0%}) vs capex {v['capex']:.0%}"
        for k, v in results.items()
    )
    c.as_of = max(v["as_of"] for v in results.values())
    c.source = "Workbook (saved, reported quarters only)"
    return c


def capex_coverage_check(ttm_ratio):
    c = Check(
        "Hyperscaler capex > CFOps",
        "Capex exceeds operating cash flow",
        "Combined hyperscaler TTM capex / cash flow from operations above 100%",
    )
    now, as_of = last(ttm_ratio)
    if _ready(c, now, as_of, "Workbook (saved, reported quarters only)"):
        c.red = now > 1.0
        c.status = "Capex exceeds CFOps" if c.red else "Funded by CFOps"
        c.reading = f"{now:.0%} of CFOps"
    return c


def spread_vs_average_check(spread, average, source, independent=None):
    c = Check(
        "Tech HY spreads",
        "Widening above average",
        "Sponsor HY Tech − IG spread above its saved average; FRED HY − IG OAS proxy otherwise",
    )
    now, as_of = last(spread)
    avg, _ = last(average)
    if _ready(c, avg, as_of, source) and not np.isnan(now):
        c.red = now > avg
        c.status = "Above average" if c.red else "Below average"
        c.reading = f"{now:.2f} vs average {avg:.2f}"
    elif independent is not None:
        diff = clean(independent)
        now, as_of = last(diff)
        avg = float(diff.mean()) if len(diff) else np.nan
        if _ready(c, avg, as_of, "FRED proxy: BAMLH0A0HYM2 − BAMLC0A0CM") and not np.isnan(now):
            c.red = now > avg
            c.status = "Above average" if c.red else "Below average"
            c.reading = (
                f"{now * 100:.0f} bp vs {avg * 100:.0f} bp average of retained history "
                f"(since {diff.index[0].date()})"
            )
    return c


def relative_strength_check(series_by_name, months=3):
    c = Check(
        "Leveraged cloud companies underperform",
        "Relative strength falling",
        f"Every tracked name's price relative to the S&P 500 lower than {months} months earlier",
    )
    changes, dates = {}, []
    for name, series in series_by_name.items():
        s = clean(series)
        if len(s) <= months:
            continue
        changes[name] = s.iloc[-1] / s.iloc[-1 - months] - 1 if s.iloc[-1 - months] else np.nan
        dates.append(s.index[-1].date())
    changes = {k: v for k, v in changes.items() if not np.isnan(v)}
    if changes:
        c.red = all(v < 0 for v in changes.values())
        c.status = "Underperforming" if c.red else "Not uniformly underperforming"
        c.reading = "; ".join(f"{k} {v:+.0%} vs S&P over {months}M" for k, v in changes.items())
        c.as_of = max(dates)
        c.source = "Workbook (saved monthly relative strength)"
    return c


def liquidity_check(nfci, lending_standards):
    c = Check(
        "Lower liquidity (AI lab IPO delays)",
        "Tightening liquidity",
        "Proxy: Chicago Fed NFCI more than 0.25 (index SD units) tighter than a year ago AND net "
        "share of banks tightening C&I standards above 0. IPO timing itself needs analyst judgment",
    )
    change = change_over(nfci, 12, GAP["weekly"])
    now, as_of = last(nfci)
    standards, _ = last(lending_standards)
    if _ready(c, change, as_of, "FRED proxy: NFCI, DRTSCILM") and not np.isnan(standards):
        c.red = bool(change > NFCI_TIGHTENING and standards > 0)
        c.status = "Tightening" if c.red else "Not materially tightening"
        c.reading = (
            f"NFCI {now:+.2f} ({change:+.2f} Y/Y); net {standards:+.1f}% of banks tightening C&I"
        )
    return c


def funding_gap(capex, operating_cash_flow):
    """Capex minus operating cash flow on matching quarter dates (positive = external need)."""
    pair = pd.concat([clean(capex), clean(operating_cash_flow)], axis=1, keys=["c", "o"]).dropna()
    return pair["c"] - pair["o"]


def checks_frame(checks):
    rows = [c.row() for c in checks]
    frame = pd.DataFrame(rows)
    return frame.rename(
        columns={
            "metric": "Metric",
            "warning_reading": "Warning reading",
            "reading": "Current reading",
            "status": "Status",
            "signal": "Signal",
            "as_of": "As of",
            "source": "Source",
            "rule": "Rule",
        }
    )[
        [
            "Metric",
            "Warning reading",
            "Current reading",
            "Status",
            "Signal",
            "As of",
            "Source",
            "Rule",
        ]
    ]
