"""Point-in-time BTC asset coverage calculations for the workbook's BTC sheet."""

import math


def coverage_snapshot(holdings_btc, btc_price_usd, debt_usd, preferred_usd, cost_basis_usd):
    """Compute workbook coverage formulas from one dated fundamentals snapshot.

    All monetary inputs are USD; ``cost_basis_usd`` is the average acquisition
    cost per BTC, not aggregate cost. Amount outputs ending in ``usdm`` are USD
    millions. Percent outputs are percentage points (40 means 40%). This is a
    static coverage sensitivity, not historical holdings or a solvency model.
    """
    inputs = {
        "holdings_btc": holdings_btc,
        "btc_price_usd": btc_price_usd,
        "debt_usd": debt_usd,
        "preferred_usd": preferred_usd,
        "cost_basis_usd": cost_basis_usd,
    }
    values = {}
    for name, value in inputs.items():
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite number")  # noqa: TRY004
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} must be a finite number") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite number")
        if name in {"debt_usd", "preferred_usd"}:
            if number < 0:
                raise ValueError(f"{name} must be nonnegative")
        elif number <= 0:
            raise ValueError(f"{name} must be positive")
        values[name] = number

    holdings = values["holdings_btc"]
    price = values["btc_price_usd"]
    claims = values["debt_usd"] + values["preferred_usd"]
    market_value = holdings * price
    if claims <= 0:
        raise ValueError("Debt plus preferred stock must be positive for coverage calculations")
    if not math.isfinite(claims) or not math.isfinite(market_value) or market_value <= 0:
        raise ValueError("BTC market value and total claims must be finite")

    threshold = claims / holdings
    result = {
        **values,
        "btc_market_value_usdm": market_value / 1_000_000,
        "debt_preferred_usdm": claims / 1_000_000,
        "ltv_pct": claims / market_value * 100,
        "coverage_x": market_value / claims,
        "breakeven_btc_price_usd": threshold,
        "downside_pct": (threshold / price - 1) * 100,
        "gain_loss_usdm": (price - values["cost_basis_usd"]) * holdings / 1_000_000,
    }
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError("Coverage calculations produced non-finite results")
    if not math.isclose(result["ltv_pct"] / 100 * result["coverage_x"], 1, rel_tol=1e-12):
        raise ArithmeticError("LTV and coverage do not reconcile")
    if not math.isclose(threshold * holdings, claims, rel_tol=1e-12):
        raise ArithmeticError("BTC coverage price and total claims do not reconcile")
    return result
