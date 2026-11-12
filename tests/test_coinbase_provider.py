import httpx
import pandas as pd
import pytest

from src.providers import coinbase
from src.providers.coinbase import SERIES_ID, SPOT_SERIES_ID, CoinbaseProvider, parse_candles

# Public API response verified 2026-10-22 for 2024-01-01 through 2024-01-03.
PUBLIC_CANDLES = [
    [1704240000, 40625.68, 45519.32, 44972.81, 42862.44, 32281.85234351],
    [1704153600, 44195.13, 45925.82, 44220.78, 44972.8, 29583.38407747],
    [1704067200, 42175.65, 44240.8, 42288.58, 44220.78, 7977.72851143],
]


def candle(date, close=100.0):
    timestamp = int(pd.Timestamp(date, tz="UTC").timestamp())
    return [timestamp, 90.0, 110.0, 95.0, close, 10.0]


def response(payload, status=200):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", coinbase.URL))


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(coinbase, "_utc_today", lambda: pd.Timestamp("2026-10-22", tz="UTC"))
    monkeypatch.setattr(coinbase, "_utc_now", lambda: pd.Timestamp("2026-10-22T12:00:00Z"))
    monkeypatch.setattr(coinbase.time, "sleep", lambda seconds: None)


def test_documented_live_response_shape_and_close_selection(monkeypatch):
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(PUBLIC_CANDLES))
    result = CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-01-03")
    assert result.index.tolist() == list(pd.date_range("2024-01-01", "2024-01-03"))
    assert result.tolist() == [44220.78, 44972.8, 42862.44]
    assert result.index.tz is None
    assert result.name == SERIES_ID


def test_pagination_never_exceeds_300_days_and_does_not_fill_gaps(monkeypatch):
    calls = []
    dates = ["2024-01-01", "2024-10-26", "2024-10-27", "2024-11-01"]

    def fake_get(url, **kwargs):
        assert url == coinbase.URL
        params = kwargs["params"]
        assert params["granularity"] == 86400
        start, end = pd.Timestamp(params["start"]), pd.Timestamp(params["end"])
        assert end - start < pd.Timedelta(days=300)
        calls.append((start, end))
        return response(
            [candle(date) for date in dates if start <= pd.Timestamp(date, tz="UTC") <= end]
        )

    monkeypatch.setattr(coinbase.httpx, "get", fake_get)
    result = CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-11-01")
    assert len(calls) == 2
    assert calls[1][0] == calls[0][1] + pd.Timedelta(seconds=1)
    assert result.index.tolist() == [pd.Timestamp(date) for date in dates]


def test_current_utc_candle_and_rows_outside_requested_range_are_removed(monkeypatch):
    payload = [candle("2026-10-20"), candle("2026-10-21"), candle("2026-10-22")]
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(payload))
    result = CoinbaseProvider().get_history(SERIES_ID, "2026-10-21", "2026-10-30")
    assert result.index.tolist() == [pd.Timestamp("2026-10-21")]


def test_both_requested_boundaries_are_inclusive(monkeypatch):
    payload = [candle("2024-01-01"), candle("2024-01-02"), candle("2024-01-03")]
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(payload))
    result = CoinbaseProvider().get_history(SERIES_ID, "2024-01-02", "2024-01-02")
    assert result.index.tolist() == [pd.Timestamp("2024-01-02")]


def test_default_start_and_completed_day_cutoff(monkeypatch):
    requests = []

    def fake_request(self, start, end):
        requests.append((start, end))
        return [candle("2026-10-21")]

    monkeypatch.setattr(CoinbaseProvider, "_request", fake_request)
    result = CoinbaseProvider().get_history(SERIES_ID)
    assert requests[0][0] == pd.Timestamp("2015-07-20", tz="UTC")
    assert requests[-1][1] == pd.Timestamp("2026-10-21T23:59:59Z")
    assert result.iloc[-1] == 100.0


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_http_status_is_retried(monkeypatch, status):
    replies = iter([response({}, status), response([candle("2024-01-01")])])
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: next(replies))
    result = CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-01-01")
    assert result.iloc[0] == 100.0


@pytest.mark.parametrize("error", ["status", "network"])
def test_failure_retries_are_bounded(monkeypatch, error):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        if error == "network":
            raise httpx.ConnectError("unavailable")
        return response({}, 503)

    monkeypatch.setattr(coinbase.httpx, "get", fake_get)
    with pytest.raises((httpx.ConnectError, httpx.HTTPStatusError)):
        CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-01-01")
    assert len(calls) == 3


def test_non_retryable_http_error_fails_immediately(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        return response({}, 404)

    monkeypatch.setattr(coinbase.httpx, "get", fake_get)
    with pytest.raises(httpx.HTTPStatusError):
        CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-01-01")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"message": "error"}, "array"),
        ([[1704067200, 90, 110, 95, 100]], "six"),
        ([[1704067200, 90, 110, 95, "100", 1]], "numeric"),
        ([[1704067200, 90, 110, 95, True, 1]], "numeric"),
        ([[1704067200, 90, float("inf"), 95, 100, 1]], "Non-finite"),
        ([[1704067200, 90, 110, 95, float("nan"), 1]], "Non-finite"),
        ([[1704067200, 0, 110, 95, 100, 1]], "positive"),
        ([[1704067200, 90, 110, 95, 100, -1]], "nonnegative"),
        ([[1704067200, 90, 110, 120, 100, 1]], "OHLC"),
        ([[1704067200, 90, 110, 95, 80, 1]], "OHLC"),
        ([[1704067201, 90, 110, 95, 100, 1]], "midnight"),
        ([candle("2026-10-23")], "future"),
    ],
)
def test_reject_invalid_source_data(payload, match):
    with pytest.raises(ValueError, match=match):
        parse_candles(payload)


def test_exact_duplicates_are_accepted_and_conflicting_duplicates_rejected():
    row = candle("2024-01-01")
    assert len(parse_candles([row, row])) == 1
    with pytest.raises(ValueError, match="Conflicting"):
        parse_candles([row, candle("2024-01-01", 101)])


def test_conflicting_duplicates_across_pages_are_rejected(monkeypatch):
    replies = iter([[candle("2024-01-01")], [candle("2024-01-01", 101)]])
    monkeypatch.setattr(CoinbaseProvider, "_request", lambda *args: next(replies))
    with pytest.raises(ValueError, match="Conflicting"):
        CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-11-01")


def test_empty_data_for_a_completed_period_is_a_failure(monkeypatch):
    monkeypatch.setattr(CoinbaseProvider, "_request", lambda *args: [])
    with pytest.raises(ValueError, match="No completed"):
        CoinbaseProvider().get_history(SERIES_ID, "2024-01-01", "2024-01-01")


def test_future_only_request_does_not_call_network(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("No request should be made for a day that is still open")

    monkeypatch.setattr(coinbase.httpx, "get", fail)
    result = CoinbaseProvider().get_history(SERIES_ID, "2026-10-22")
    assert result.empty
    assert isinstance(result.index, pd.DatetimeIndex)


def test_invalid_series_and_date_range():
    provider = CoinbaseProvider()
    with pytest.raises(ValueError, match="Unsupported"):
        provider.get_history("OTHER")
    with pytest.raises(ValueError, match="precede"):
        provider.get_history(SERIES_ID, "2024-01-02", "2024-01-01")


def test_spot_preserves_actual_source_timestamp_and_source_date(monkeypatch):
    def fake_get(url, **kwargs):
        assert url == coinbase.TICKER_URL
        return response({"price": "105010.25", "time": "2026-10-21T23:59:59.123456Z"})

    monkeypatch.setattr(coinbase.httpx, "get", fake_get)
    result = CoinbaseProvider().get_history(SPOT_SERIES_ID)
    assert result.index.tolist() == [pd.Timestamp("2026-10-21")]
    assert result.iloc[0] == 105010.25
    assert result.name == SPOT_SERIES_ID
    assert pd.Timestamp(result.attrs["published_at"]) == pd.Timestamp("2026-10-21T23:59:59.123456Z")
    assert result.attrs["quote_timestamp"] == "2026-10-21T23:59:59.123456+00:00"


@pytest.mark.parametrize(
    "payload,match",
    [
        ([], "price and time"),
        ({"price": "100"}, "price and time"),
        ({"price": "0", "time": "2026-10-22T11:00:00Z"}, "positive"),
        ({"price": "-1", "time": "2026-10-22T11:00:00Z"}, "positive"),
        ({"price": "NaN", "time": "2026-10-22T11:00:00Z"}, "finite"),
        ({"price": "inf", "time": "2026-10-22T11:00:00Z"}, "finite"),
        ({"price": True, "time": "2026-10-22T11:00:00Z"}, "finite"),
        ({"price": "100", "time": 100}, "ISO"),
        ({"price": "100", "time": "2026-10-22"}, "ISO"),
        ({"price": "100", "time": "2026-10-22T11:00:00"}, "timezone"),
        ({"price": "100", "time": "INVALIDTDATE"}, "Invalid"),
        ({"price": "100", "time": "2026-10-22T12:05:01Z"}, "future"),
    ],
)
def test_spot_invalid_data_is_rejected(monkeypatch, payload, match):
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(payload))
    with pytest.raises(ValueError, match=match):
        CoinbaseProvider().get_history(SPOT_SERIES_ID)


def test_spot_permits_bounded_server_clock_skew(monkeypatch):
    payload = {"price": "100", "time": "2026-10-22T12:04:00Z"}
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(payload))
    assert CoinbaseProvider().get_history(SPOT_SERIES_ID).iloc[0] == 100


def test_spot_does_not_imply_historical_availability(monkeypatch):
    payload = {"price": "100", "time": "2026-10-22T11:00:00Z"}
    monkeypatch.setattr(coinbase.httpx, "get", lambda *args, **kwargs: response(payload))
    with pytest.raises(ValueError, match="outside"):
        CoinbaseProvider().get_history(SPOT_SERIES_ID, "2024-01-01", "2024-01-31")
