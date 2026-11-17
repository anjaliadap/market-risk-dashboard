"""Small, bounded downloader for the official public workbooks."""

import time

import httpx


class PublicSourceError(RuntimeError):
    """A public source is unavailable; callers must retain existing observations."""


def fetch_workbook(url: str, *, legacy_xls: bool = False) -> bytes:
    """Fetch a workbook without credentials or bypassing source access restrictions."""
    for attempt in range(3):
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": "MarketRiskDashboard/0.1 (public data refresh)"},
                timeout=30,
                follow_redirects=True,
            )
            response.raise_for_status()
            content = response.content
            signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" if legacy_xls else b"PK\x03\x04"
            if not content.startswith(signature):
                raise PublicSourceError(
                    f"{url} returned an access/error page or an unsupported file, not the "
                    "expected workbook; existing observations must be retained"
                )
            if len(content) > 10_000_000:
                raise PublicSourceError(f"Unexpected workbook size from {url}")
            return content
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retriable = not isinstance(exc, httpx.ProxyError) and (
                not isinstance(exc, httpx.HTTPStatusError)
                or exc.response.status_code in {429, 500, 502, 503, 504}
            )
            if attempt == 2 or not retriable:
                raise PublicSourceError(
                    f"Public source unavailable: {url}; existing observations must be retained "
                    f"({type(exc).__name__})"
                ) from exc
            time.sleep(2**attempt)
    raise PublicSourceError(f"Public source unavailable: {url}")  # pragma: no cover


def filter_history(series, start_date, end_date):
    """Apply inclusive request bounds without filling or extrapolating data."""
    import pandas as pd

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None
    if pd.isna(start) or (end is not None and (pd.isna(end) or end < start)):
        raise ValueError("Invalid history date bounds")
    selected = series.loc[series.index >= start]
    if end is not None:
        selected = selected.loc[selected.index <= end]
    return selected
