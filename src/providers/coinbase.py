"""Public Coinbase Exchange BTC/USD completed daily closing prices.

The source is exchange spot trading, not the Bloomberg Bitcoin index. Dates
identify the start of a UTC day; its close is known only after that day ends.
Missing source candles are never filled or replaced with invented observations.
"""

import math
import time

import httpx
import pandas as pd

URL = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
TICKER_URL = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
SERIES_ID = "COINBASE_BTC_USD"
SPOT_SERIES_ID = "COINBASE_BTC_SPOT"
DEFAULT_START = "2015-07-20"
GRANULARITY = 86400
MAX_CANDLES = 300


def _utc_now():
    return pd.Timestamp.now(tz="UTC")


def _utc_today():
    return _utc_now().normalize()


def _date_utc(value):
    date = pd.Timestamp(value)
    if pd.isna(date):
        raise ValueError("A valid date is required")
    if date.tzinfo is None:
        date = date.tz_localize("UTC")
    return date.tz_convert("UTC").normalize()


def parse_candles(payload, today=None):
    """Validate the documented six-field candle rows, keyed by UTC day.

    Exact repeated rows are harmless pagination overlap. Repeated timestamps
    with any differing OHLCV field are rejected to avoid silently choosing data.
    The current, still-open UTC candle may be present; callers remove it.
    """
    if not isinstance(payload, list):
        raise ValueError("Coinbase returned an object instead of a candle array")  # noqa: TRY004
    cutoff = _utc_today() if today is None else _date_utc(today)
    candles = {}
    for row in payload:
        if not isinstance(row, (list, tuple)) or len(row) != 6:
            raise ValueError("Expected six fields per Coinbase OHLCV candle")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in row):
            raise ValueError("Coinbase candle fields must be numeric")
        if any(not math.isfinite(value) for value in row):
            raise ValueError("Non-finite Coinbase candle value")
        timestamp, low, high, opening, close, volume = row
        if timestamp != int(timestamp) or timestamp % GRANULARITY:
            raise ValueError("Coinbase daily candle timestamp must be UTC midnight")
        try:
            date = pd.Timestamp(timestamp, unit="s", tz="UTC")
        except (ValueError, OverflowError) as exc:
            raise ValueError("Invalid Coinbase candle timestamp") from exc
        if date > cutoff:
            raise ValueError("Coinbase returned a future daily candle")
        if min(low, high, opening, close) <= 0 or volume < 0:
            raise ValueError("Coinbase prices must be positive and volume nonnegative")
        if not (low <= opening <= high and low <= close <= high):
            raise ValueError("Coinbase candle prices violate OHLC bounds")
        values = tuple(float(value) for value in row[1:])
        if date in candles and candles[date] != values:
            raise ValueError("Conflicting Coinbase candles for the same date")
        candles[date] = values
    return candles


class CoinbaseProvider:
    """Fetch public daily candles in at most 300-day requests without API keys."""

    def __init__(self, request_interval=0.2):
        if request_interval < 0:
            raise ValueError("request_interval must be nonnegative")
        self.request_interval = request_interval

    def _request(self, start, end):
        params = {
            "granularity": GRANULARITY,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
        }
        return self._request_json(URL, params)

    def _request_json(self, url, params=None):
        for attempt in range(3):
            try:
                response = httpx.get(
                    url,
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": "MarketRiskMonitor/1.0"},
                    timeout=30,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == 2 or isinstance(exc, httpx.ProxyError):
                    raise
                if isinstance(exc, httpx.HTTPStatusError) and not (
                    exc.response.status_code == 429 or 500 <= exc.response.status_code < 600
                ):
                    raise
                time.sleep(2**attempt)

    def get_spot(self):
        """Return the last traded price with the source's actual quote time.

        This is a refreshable snapshot, not a reconstructed intraday history.
        Small server clock skew of at most five minutes is tolerated.
        """
        payload = self._request_json(TICKER_URL)
        if not isinstance(payload, dict) or "price" not in payload or "time" not in payload:
            raise ValueError("Coinbase ticker must contain price and time")
        raw_price = payload["price"]
        if isinstance(raw_price, bool):
            raise ValueError("Coinbase spot price must be positive and finite")  # noqa: TRY004
        try:
            price = float(raw_price)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Coinbase spot price must be positive and finite") from exc
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Coinbase spot price must be positive and finite")
        raw_timestamp = payload["time"]
        if not isinstance(raw_timestamp, str) or "T" not in raw_timestamp:
            raise ValueError("Coinbase ticker time must be an ISO timestamp with a timezone")
        try:
            quote_time = pd.Timestamp(raw_timestamp)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Invalid Coinbase ticker timestamp") from exc
        if pd.isna(quote_time) or quote_time.tzinfo is None:
            raise ValueError("Coinbase ticker time must include a timezone")
        quote_time = quote_time.tz_convert("UTC")
        if quote_time > _utc_now() + pd.Timedelta(minutes=5):
            raise ValueError("Coinbase ticker timestamp is in the future")
        result = pd.Series(
            [price],
            index=pd.DatetimeIndex([quote_time.normalize().tz_localize(None)]),
            name=SPOT_SERIES_ID,
        )
        result.attrs["published_at"] = quote_time.to_pydatetime(warn=False)
        result.attrs["quote_timestamp"] = quote_time.isoformat()
        return result

    def get_history(self, series_id, start_date=DEFAULT_START, end_date=None):
        if series_id not in {SERIES_ID, SPOT_SERIES_ID}:
            raise ValueError(f"Unsupported Coinbase series: {series_id}")
        today = _utc_today()
        start = _date_utc(start_date)
        requested_end = _date_utc(end_date) if end_date is not None else today
        if requested_end < start:
            raise ValueError("end_date must not precede start_date")
        if series_id == SPOT_SERIES_ID:
            spot = self.get_spot()
            quote_date = spot.index[0].tz_localize("UTC")
            if not start <= quote_date <= requested_end:
                raise ValueError("Latest Coinbase quote is outside the requested date range")
            return spot
        end = min(requested_end, today - pd.Timedelta(days=1))
        if start > end:
            return pd.Series(dtype=float, index=pd.DatetimeIndex([]), name=series_id)
        candles = {}
        cursor = start
        while cursor <= end:
            last_day = min(cursor + pd.Timedelta(days=MAX_CANDLES - 1), end)
            # Inclusive day ranges remain below the API's 300-candle limit.
            response_end = last_day + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            batch = parse_candles(self._request(cursor, response_end), today=today)
            for date, values in batch.items():
                if date in candles and candles[date] != values:
                    raise ValueError("Conflicting Coinbase candles across requests")
                candles[date] = values
            cursor = last_day + pd.Timedelta(days=1)
            if cursor <= end:
                time.sleep(self.request_interval)
        closes = {
            date.tz_localize(None): values[3]
            for date, values in candles.items()
            if start <= date <= end
        }
        if not closes:
            raise ValueError("No completed daily Bitcoin observations in the requested range")
        return pd.Series(closes, dtype=float, name=series_id).sort_index()

    def get_latest(self, series_id):
        return self.get_history(series_id, _utc_today() - pd.Timedelta(days=7)).iloc[-1]

    def get_metadata(self, series_id):
        from src.registry import BY_ID

        return BY_ID[series_id]
