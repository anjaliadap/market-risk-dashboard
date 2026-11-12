"""Provider routing and atomic groups for the three workbook sections."""

import numpy as np
import pandas as pd

from src.providers.fred import FredProvider

AAII_IDS = ("AAII_BULLISH", "AAII_NEUTRAL", "AAII_BEARISH", "AAII_SP500_WEEKLY_CLOSE")
STRATEGY_IDS = (
    "STRATEGY_BTC_HOLDINGS",
    "STRATEGY_DEBT_USD",
    "STRATEGY_PREFERRED_USD",
    "STRATEGY_BTC_COST_USD",
)
SECTION_IDS = (
    "FINRA_MARGIN_DEBT",
    "GDP",
    "BOGZ1LM883164115Q",
    *AAII_IDS,
    "COINBASE_BTC_SPOT",
    *STRATEGY_IDS,
)


def group_key(series_id):
    if series_id in AAII_IDS:
        return AAII_IDS[0]
    if series_id in STRATEGY_IDS:
        return STRATEGY_IDS[0]
    return series_id


def group_ids(series_id):
    if series_id in AAII_IDS:
        return AAII_IDS
    if series_id in STRATEGY_IDS:
        return STRATEGY_IDS
    return (series_id,)


def validate_history(series, meta):
    """Reject a failed/changed source before the database transaction begins."""
    if not isinstance(series, pd.Series) or series.empty:
        raise ValueError(f"No observations for {meta['id']}")
    if not isinstance(series.index, pd.DatetimeIndex) or series.index.hasnans:
        raise ValueError("A valid date index is required")
    clean = series.dropna().astype(float).sort_index()
    if clean.empty or not np.isfinite(clean).all():
        raise ValueError("No finite observations")
    if clean.index.duplicated().any() or clean.index.normalize().duplicated().any():
        raise ValueError("Duplicate observation dates")
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    if clean.index.tz is not None:
        raise ValueError("Observation dates must be timezone-naive; quote times are separate")
    if (clean.index > today).any():
        raise ValueError("Future observation date")
    if "min_value" in meta and (clean < meta["min_value"]).any():
        raise ValueError("Observation below permitted minimum")
    clean.attrs = series.attrs.copy()
    return clean


def fetch_group(series_id):
    """All related fields are parsed and validated from one source snapshot."""
    if series_id in AAII_IDS:
        from src.providers.aaii import AaiiProvider

        frame = AaiiProvider().get_frame()
        return {key: frame[key].dropna() for key in AAII_IDS}
    if series_id in STRATEGY_IDS:
        from src.providers.strategy import StrategyProvider

        frame = StrategyProvider().get_frame()
        return {key: frame[key].dropna() for key in STRATEGY_IDS}
    if series_id == "FINRA_MARGIN_DEBT":
        from src.providers.finra import FinraProvider

        return {series_id: FinraProvider().get_history(series_id)}
    if series_id.startswith("COINBASE_"):
        from src.providers.coinbase import CoinbaseProvider

        return {series_id: CoinbaseProvider().get_history(series_id)}
    start = "1997-01-01" if series_id == "BOGZ1LM883164115Q" else "2000-01-01"
    return {series_id: FredProvider().get_history(series_id, start_date=start)}
