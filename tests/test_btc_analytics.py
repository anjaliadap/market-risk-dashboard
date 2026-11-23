import math

import pytest

from src.analytics.btc import coverage_snapshot

BASE = {
    "holdings_btc": 500_000,
    "btc_price_usd": 100_000,
    "debt_usd": 8_000_000_000,
    "preferred_usd": 2_000_000_000,
    "cost_basis_usd": 75_000,
}


def test_workbook_snapshot_formulas_and_units():
    result = coverage_snapshot(**BASE)
    assert result["btc_market_value_usdm"] == 50_000
    assert result["debt_preferred_usdm"] == 10_000
    assert result["ltv_pct"] == 20
    assert result["coverage_x"] == 5
    assert result["breakeven_btc_price_usd"] == 20_000
    assert result["downside_pct"] == -80
    assert result["gain_loss_usdm"] == 12_500
    assert result["holdings_btc"] == BASE["holdings_btc"]
    assert result["cost_basis_usd"] == BASE["cost_basis_usd"]


def test_reconciliation_and_price_sensitivity():
    current = coverage_snapshot(**BASE)
    halved = coverage_snapshot(**{**BASE, "btc_price_usd": 50_000})
    claims = BASE["debt_usd"] + BASE["preferred_usd"]
    for result in [current, halved]:
        assert result["ltv_pct"] / 100 * result["coverage_x"] == pytest.approx(1)
        assert result["breakeven_btc_price_usd"] * result["holdings_btc"] == pytest.approx(claims)
    assert halved["coverage_x"] == current["coverage_x"] / 2
    assert halved["ltv_pct"] == current["ltv_pct"] * 2
    assert halved["breakeven_btc_price_usd"] == current["breakeven_btc_price_usd"]
    assert halved["gain_loss_usdm"] == -12_500


def test_undercovered_position_reports_upside_required_without_sign_clipping():
    result = coverage_snapshot(**{**BASE, "btc_price_usd": 10_000})
    assert result["coverage_x"] == 0.5
    assert result["ltv_pct"] == 200
    assert result["downside_pct"] == 100


@pytest.mark.parametrize("key", ["holdings_btc", "btc_price_usd", "cost_basis_usd"])
@pytest.mark.parametrize("value", [0, -1])
def test_positive_inputs_required(key, value):
    with pytest.raises(ValueError, match="positive"):
        coverage_snapshot(**{**BASE, key: value})


@pytest.mark.parametrize("key", ["debt_usd", "preferred_usd"])
def test_negative_claims_rejected_but_individual_zero_allowed(key):
    with pytest.raises(ValueError, match="nonnegative"):
        coverage_snapshot(**{**BASE, key: -1})
    assert math.isfinite(coverage_snapshot(**{**BASE, key: 0})["coverage_x"])


@pytest.mark.parametrize("key", BASE)
@pytest.mark.parametrize("value", [float("inf"), float("nan"), None, True, "invalid"])
def test_nonfinite_or_invalid_inputs_are_rejected(key, value):
    with pytest.raises(ValueError, match="finite"):
        coverage_snapshot(**{**BASE, key: value})


def test_zero_total_claims_are_not_masked_as_infinite_coverage():
    with pytest.raises(ValueError, match="Debt plus preferred"):
        coverage_snapshot(**{**BASE, "debt_usd": 0, "preferred_usd": 0})


def test_overflow_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        coverage_snapshot(**{**BASE, "holdings_btc": 1e308, "btc_price_usd": 1e308})
