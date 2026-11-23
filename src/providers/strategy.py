"""Strategy's dated public BTC treasury and Ledger data, fetched as one snapshot.

Source: the same public Contentstack delivery service used by strategy.com.
These public read-only delivery identifiers are published in the site's client
bundle. They are not user credentials and grant no write access. Authenticated
Download Metric Data exports and rounded market-price KPI data are not used.
"""

import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx
import pandas as pd

from src.providers.public_http import PublicSourceError, filter_history

CONTENT_BASE = "https://cdn.contentstack.io/v3/content_types"
TRACKER_URL = f"{CONTENT_BASE}/btc_tracker/entries"
LEDGER_URL = f"{CONTENT_BASE}/bitcoin_transaction/entries"
# Public website delivery configuration; optional overrides allow normal
# maintenance after Strategy rotates its public content-delivery identifiers.
PUBLIC_API_KEY = "bltf8d808d9b8cebd37"
PUBLIC_DELIVERY_TOKEN = "cse2b77d59e6d2b5a235e96f3d"
SERIES_IDS = (
    "STRATEGY_BTC_HOLDINGS",
    "STRATEGY_DEBT_USD",
    "STRATEGY_PREFERRED_USD",
    "STRATEGY_BTC_COST_USD",
)


def _number(value, label, *, allow_zero=False):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Missing or invalid Strategy {label}")
    text = str(value).strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError(f"Missing or invalid Strategy {label}")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Strategy {label}") from exc
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"Invalid Strategy {label}")
    return float(result)


def _source_date(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Invalid Strategy {label} date")
    return pd.Timestamp(datetime.strptime(value, "%Y-%m-%d"))


def _entries(payload, label):
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("entries"), list)
        or not payload["entries"]
        or not all(isinstance(x, dict) for x in payload["entries"])
    ):
        raise ValueError(f"Missing Strategy {label} published entries")
    return payload["entries"]


def parse_snapshot(statistics, transactions, *, retrieved_at=None):
    """Reconcile the current treasury snapshot with the last Ledger cost basis.

    Statistics debt and preferred are already USD. Ledger average_price is the
    portfolio average acquisition cost USD/BTC for BTC held, excluding sold BTC.
    It is not the latest transaction's purchase_price. Ledger total_acquisition_cost
    is USD millions and supplies an independent rounding-aware check.
    """
    retrieved = pd.Timestamp(retrieved_at or datetime.now(UTC))
    if retrieved.tzinfo is None:
        retrieved = retrieved.tz_localize("UTC")
    else:
        retrieved = retrieved.tz_convert("UTC")
    records = _entries(statistics, "statistics")
    current = [entry for entry in records if entry.get("latest") is True]
    if len(current) != 1:
        raise ValueError("Expected exactly one latest Strategy statistics record")
    stats = current[0]
    stats_date = _source_date(stats.get("as_of_date"), "statistics as-of")
    ledger = _entries(transactions, "ledger")
    ledger_dates = [
        _source_date(entry.get("date_of_purchase"), "ledger reported") for entry in ledger
    ]
    latest_ledger_date = max(ledger_dates)
    latest = [entry for entry, date in zip(ledger, ledger_dates) if date == latest_ledger_date]
    if len(latest) != 1:
        raise ValueError("Expected exactly one latest Strategy ledger record")
    transaction = latest[0]
    if latest_ledger_date > stats_date:
        raise ValueError("Strategy ledger is newer than treasury statistics; snapshot not ingested")
    if stats_date > retrieved.tz_localize(None).normalize():
        raise ValueError("Strategy contains a future source date")
    holdings = _number(stats.get("btc_holdings"), "BTC holdings")
    ledger_holdings = _number(transaction.get("btc_holdings"), "ledger BTC holdings")
    debt = _number(stats.get("debt"), "convertible-debt principal USD", allow_zero=True)
    preferred = _number(stats.get("pref"), "preferred notional USD", allow_zero=True)
    average_cost = _number(transaction.get("average_price"), "average BTC cost USD/BTC")
    aggregate_cost = (
        _number(transaction.get("total_acquisition_cost"), "aggregate acquisition cost ($M)") * 1e6
    )
    if holdings > 21_000_000 or debt + preferred <= 0:
        raise ValueError("Invalid Strategy BTC holdings or combined debt/preferred")
    if holdings != ledger_holdings:
        raise ValueError(
            "Strategy statistics and ledger BTC holdings disagree; snapshot not ingested"
        )
    # The public Ledger reports average_price to whole dollars and total cost to
    # whole $M. Permit only the uncertainty implied by those two roundings.
    if abs(holdings * average_cost - aggregate_cost) > holdings * 0.5 + 500_000:
        raise ValueError("Strategy average and aggregate acquisition costs do not reconcile")
    updates = {}
    for name, entry in (("statistics", stats), ("ledger", transaction)):
        raw = entry.get("updated_at")
        if raw:
            updated = pd.to_datetime(raw, utc=True, errors="raise")
            if pd.isna(updated) or updated.to_pydatetime() > retrieved.to_pydatetime() + timedelta(
                minutes=5
            ):
                raise ValueError(f"Invalid or future Strategy {name} update timestamp")
            updates[name] = updated.isoformat()
    frame = pd.DataFrame(
        [[holdings, debt, preferred, average_cost]],
        columns=SERIES_IDS,
        index=pd.DatetimeIndex([stats_date], name="date"),
    )
    frame.attrs.update(
        {
            "retrieved_at_utc": retrieved.isoformat(),
            "observation_date_semantics": "Strategy published statistics as_of_date; Ledger cost basis reconciled by BTC holdings",
            "underlying_financial_as_of": stats_date.date().isoformat(),
            "company_reported_date": latest_ledger_date.date().isoformat(),
            "company_reported_date_semantics": "Strategy Ledger's published date; not a fiscal-period end",
            "component_as_of_dates": {
                "STRATEGY_BTC_HOLDINGS": stats_date.date().isoformat(),
                "STRATEGY_DEBT_USD": stats_date.date().isoformat(),
                "STRATEGY_PREFERRED_USD": stats_date.date().isoformat(),
                "STRATEGY_BTC_COST_USD": latest_ledger_date.date().isoformat(),
            },
            "cost_basis_date_matches_statistics": latest_ledger_date == stats_date,
            "source_updated_at_utc": updates,
            "source_urls": [TRACKER_URL, LEDGER_URL],
            "debt_definition": "Aggregate principal of outstanding convertible debt, USD",
            "preferred_definition": "Aggregate USD notional of outstanding perpetual preferred stock",
            "cost_definition": "Average acquisition cost USD/BTC for BTC held; sold BTC excluded",
        }
    )
    return frame


def _fetch_entries(url, *, params):
    headers = {
        "User-Agent": "MarketRiskDashboard/0.1 (public data refresh)",
        "api_key": os.environ.get("STRATEGY_PUBLIC_CONTENT_API_KEY", PUBLIC_API_KEY),
        "access_token": os.environ.get(
            "STRATEGY_PUBLIC_CONTENT_DELIVERY_TOKEN", PUBLIC_DELIVERY_TOKEN
        ),
    }
    for attempt in range(3):
        try:
            response = httpx.get(
                url, params=params, headers=headers, timeout=30, follow_redirects=True
            )
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                raise PublicSourceError("Unexpected Strategy source response size")
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retry = not isinstance(exc, httpx.ProxyError) and (
                not isinstance(exc, httpx.HTTPStatusError)
                or exc.response.status_code in {429, 500, 502, 503, 504}
            )
            if attempt == 2 or not retry:
                raise PublicSourceError(
                    "Strategy public source unavailable; retain the prior complete snapshot "
                    f"({type(exc).__name__}). Check the site's public delivery configuration."
                ) from exc
            time.sleep(2**attempt)
        except ValueError as exc:
            raise PublicSourceError("Strategy did not return valid public JSON") from exc
    raise PublicSourceError("Strategy public source unavailable")  # pragma: no cover


class StrategyProvider:
    """Fetch all company inputs together; never silently reuse one old component.

    Returns the latest complete dated snapshot. Repeated refreshes accumulate
    observations locally; this does not reconstruct pre-installation history.
    Ledger basis can predate an independent debt/preferred update only when the
    published BTC holding count still matches, with both dates carried in attrs.
    """

    def get_frame(self, start_date="2000-01-01", end_date=None):
        filter_history(pd.DataFrame(index=pd.DatetimeIndex([])), start_date, end_date)
        common = {"environment": "production", "locale": "en", "limit": 2}
        statistics = _fetch_entries(
            TRACKER_URL,
            params={
                **common,
                "query": json.dumps({"latest": True}),
                "desc": "as_of_date",
            },
        )
        transactions = _fetch_entries(LEDGER_URL, params={**common, "desc": "date_of_purchase"})
        try:
            frame = parse_snapshot(statistics, transactions)
        except (ValueError, TypeError, KeyError) as exc:
            raise PublicSourceError(
                f"Strategy snapshot failed validation: {exc}; retain the prior complete snapshot"
            ) from exc
        return filter_history(frame, start_date, end_date)

    def get_history(self, series_id, start_date="2000-01-01", end_date=None):
        if series_id not in SERIES_IDS:
            raise ValueError(f"Unsupported Strategy series: {series_id}")
        return self.get_frame(start_date, end_date)[series_id].rename(series_id)

    def get_latest(self, series_id):
        return self.get_history(series_id).iloc[-1]

    def get_metadata(self, series_id):
        from src.registry import BY_ID

        return BY_ID[series_id]
