"""Small source-derived fixtures retain the public datasets' fields and units."""

from copy import deepcopy

import httpx
import pandas as pd
import pytest

from src.providers import strategy
from src.providers.public_http import PublicSourceError

STATS = {
    "entries": [
        {
            "latest": True,
            "as_of_date": "2026-10-19",
            "debt": 6_714_000_000,
            "pref": 13_556_668_500,
            "btc_holdings": 848_517,
            "updated_at": "2026-10-19T12:03:49.479Z",
        }
    ]
}
TRANSACTIONS = {
    "entries": [
        {
            "date_of_purchase": "2026-10-19",
            "count": 267,
            "purchase_price": 82_900,
            "btc_holdings": 848_517,
            "average_price": 75_446,
            "total_acquisition_cost": 64_017,
            "updated_at": "2026-10-19T11:49:06.683Z",
        },
        {
            "date_of_purchase": "2026-10-12",
            "btc_holdings": 848_250,
            "average_price": 75_444,
            "total_acquisition_cost": 63_995,
        },
    ]
}
RETRIEVED = "2026-10-22T21:16:00Z"


def test_snapshot_preserves_exact_dollar_units_and_cost_meaning():
    frame = strategy.parse_snapshot(STATS, TRANSACTIONS, retrieved_at=RETRIEVED)
    assert list(frame.columns) == list(strategy.SERIES_IDS)
    row = frame.iloc[0]
    assert row["STRATEGY_BTC_HOLDINGS"] == 848_517
    assert row["STRATEGY_DEBT_USD"] == 6_714_000_000
    assert row["STRATEGY_PREFERRED_USD"] == 13_556_668_500
    assert row["STRATEGY_BTC_COST_USD"] == 75_446
    assert row["STRATEGY_BTC_COST_USD"] != 82_900
    assert frame.index[0] == pd.Timestamp("2026-10-19")
    assert frame.attrs["retrieved_at_utc"] == "2026-10-22T21:16:00+00:00"
    assert frame.attrs["company_reported_date"] == "2026-10-19"
    assert frame.attrs["cost_basis_date_matches_statistics"]


def test_source_dates_may_differ_for_independent_debt_update():
    changed = deepcopy(STATS)
    changed["entries"][0]["as_of_date"] = "2026-10-21"
    frame = strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)
    assert frame.index[0] == pd.Timestamp("2026-10-21")
    assert frame.attrs["component_as_of_dates"]["STRATEGY_BTC_COST_USD"] == "2026-10-19"
    assert frame.attrs["component_as_of_dates"]["STRATEGY_DEBT_USD"] == "2026-10-21"
    assert not frame.attrs["cost_basis_date_matches_statistics"]


def test_holdings_must_reconcile_across_datasets():
    changed = deepcopy(STATS)
    changed["entries"][0]["btc_holdings"] = 849_000
    with pytest.raises(ValueError, match="BTC holdings disagree"):
        strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)


def test_ledger_newer_than_statistics_is_not_a_coherent_snapshot():
    changed = deepcopy(STATS)
    changed["entries"][0]["as_of_date"] = "2026-10-18"
    with pytest.raises(ValueError, match="newer than"):
        strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)


def test_average_cost_reconciles_to_published_aggregate_with_rounding():
    changed = deepcopy(TRANSACTIONS)
    changed["entries"][0]["average_price"] = 82_900
    with pytest.raises(ValueError, match="acquisition costs do not reconcile"):
        strategy.parse_snapshot(STATS, changed, retrieved_at=RETRIEVED)


@pytest.mark.parametrize("value", [None, "N/A", "nan", "inf", "-1", True])
def test_bad_debt_never_becomes_zero(value):
    changed = deepcopy(STATS)
    changed["entries"][0]["debt"] = value
    with pytest.raises(ValueError):
        strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)


def test_duplicate_latest_statistics_are_ambiguous():
    with pytest.raises(ValueError, match="exactly one latest"):
        strategy.parse_snapshot(
            {"entries": STATS["entries"] * 2}, TRANSACTIONS, retrieved_at=RETRIEVED
        )


def test_duplicate_latest_ledger_is_ambiguous():
    changed = {"entries": TRANSACTIONS["entries"] * 2}
    with pytest.raises(ValueError, match="exactly one latest Strategy ledger"):
        strategy.parse_snapshot(STATS, changed, retrieved_at=RETRIEVED)


def test_future_source_and_update_dates_rejected():
    changed = deepcopy(STATS)
    changed["entries"][0]["as_of_date"] = "2026-10-25"
    with pytest.raises(ValueError, match="future source"):
        strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)
    changed = deepcopy(STATS)
    changed["entries"][0]["updated_at"] = "2026-10-25T00:00:00Z"
    with pytest.raises(ValueError, match="future Strategy statistics"):
        strategy.parse_snapshot(changed, TRANSACTIONS, retrieved_at=RETRIEVED)


def test_provider_fetches_complete_group_and_preserves_attrs(monkeypatch):
    calls = []

    def fetch(url, **kwargs):
        calls.append((url, kwargs["params"]))
        return {strategy.TRACKER_URL: STATS, strategy.LEDGER_URL: TRANSACTIONS}[url]

    monkeypatch.setattr(strategy, "_fetch_entries", fetch)
    original = strategy.parse_snapshot
    monkeypatch.setattr(
        strategy, "parse_snapshot", lambda *args: original(*args, retrieved_at=RETRIEVED)
    )
    frame = strategy.StrategyProvider().get_frame("2026-10-01", "2026-10-31")
    assert len(frame) == 1
    assert [x[0] for x in calls] == [strategy.TRACKER_URL, strategy.LEDGER_URL]
    assert '"latest": true' in calls[0][1]["query"]
    assert frame[strategy.SERIES_IDS[0]].attrs["source_urls"] == [
        strategy.TRACKER_URL,
        strategy.LEDGER_URL,
    ]
    assert strategy.StrategyProvider().get_frame("2026-10-20", "2026-10-31").empty


def test_fetch_403_does_not_retry_or_bypass(monkeypatch):
    calls = []

    def deny(url, **kwargs):
        calls.append(url)
        return httpx.Response(403, request=httpx.Request("GET", url))

    monkeypatch.setattr(strategy.httpx, "get", deny)
    with pytest.raises(PublicSourceError, match="retain"):
        strategy._fetch_entries(strategy.LEDGER_URL, params={})
    assert len(calls) == 1


def test_invalid_date_bounds_rejected_before_network(monkeypatch):
    monkeypatch.setattr(
        strategy, "_fetch_entries", lambda *a, **k: pytest.fail("Should not contact source")
    )
    with pytest.raises(ValueError, match="bounds"):
        strategy.StrategyProvider().get_frame("2026-10-22", "2026-10-01")


def test_schema_validation_wraps_source_error(monkeypatch):
    monkeypatch.setattr(strategy, "_fetch_entries", lambda *a, **k: {})
    with pytest.raises(PublicSourceError, match="snapshot failed validation"):
        strategy.StrategyProvider().get_frame()
