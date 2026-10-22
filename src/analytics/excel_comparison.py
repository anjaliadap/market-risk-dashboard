"""Independent calculation checks; these never replace sponsor saved outputs."""

import math


def compare_calculations(values):
    """values(sheet, cell) supplies saved scalars. Return validation, not financial data."""
    checks = []

    def check(name, sheet, output, calculate):
        try:
            expected = calculate()
            actual = values(sheet, output)
            good = isinstance(actual, (float, int)) and math.isclose(
                actual, expected, rel_tol=1e-8, abs_tol=1e-8
            )
            checks.append(
                {
                    "calculation": name,
                    "sheet": sheet,
                    "cell": output,
                    "status": "match" if good else "mismatch",
                }
            )
        except (ValueError, TypeError, ZeroDivisionError, OverflowError):
            checks.append(
                {"calculation": name, "sheet": sheet, "cell": output, "status": "unavailable"}
            )

    def v(sheet, cell):
        result = values(sheet, cell)
        if (
            isinstance(result, bool)
            or not isinstance(result, (int, float))
            or not math.isfinite(result)
        ):
            raise ValueError("Invalid comparison input")
        return result

    check(
        "BTC market value in USD millions",
        "BTC",
        "D6",
        lambda: v("BTC", "D4") * v("BTC", "D5") / 1_000_000,
    )
    check("BTC loan-to-value", "BTC", "D9", lambda: v("BTC", "D8") / v("BTC", "D6"))
    check("BTC debt coverage", "BTC", "D10", lambda: v("BTC", "D6") / v("BTC", "D8"))
    check(
        "Implied gold at LT ratio",
        "Gold to Oil",
        "Q23",
        lambda: v("Gold to Oil", "J463") * v("Gold to Oil", "L463"),
    )
    check(
        "Gold downside",
        "Gold to Oil",
        "Q25",
        lambda: v("Gold to Oil", "Q23") / v("Gold to Oil", "Q24") - 1,
    )
    check(
        "Implied oil at LT ratio",
        "Gold to Oil",
        "Q27",
        lambda: v("Gold to Oil", "I463") / v("Gold to Oil", "L463"),
    )
    check(
        "Oil upside",
        "Gold to Oil",
        "Q29",
        lambda: v("Gold to Oil", "Q27") / v("Gold to Oil", "Q28") - 1,
    )
    check("Treasury reciprocal yield P/E", "Valuation", "F10", lambda: 1 / v("Valuation", "F4"))
    check(
        "Equity reciprocal earnings-yield P/E", "Valuation", "F11", lambda: 1 / v("Valuation", "F9")
    )
    check(
        "Bear checklist saved fraction",
        "Bear Market",
        "D24",
        lambda: v("Bear Market", "D22") / v("Bear Market", "D23"),
    )
    check(
        "Recession saved fraction",
        "Recession",
        "F56",
        lambda: v("Recession", "F55") / v("Recession", "D55"),
    )
    return checks
