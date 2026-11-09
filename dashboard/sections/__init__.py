"""Dedicated research pages. Each module exposes ``render(ctx, render_section)``."""

from dashboard.sections import (
    banks,
    consumer,
    demand,
    financing,
    housing,
    recession,
    supply,
    valuation,
    vix_options,
)
from dashboard.sections.common import PageContext

RENDERERS = {
    "Housing": housing.render,
    "Banks": banks.render,
    "Valuation": valuation.render,
    "Consumer": consumer.render,
    "VIX & Options": vix_options.render,
    "Recession": recession.render,
    "Supply": supply.render,
    "Demand": demand.render,
    "Financing": financing.render,
}

__all__ = ["RENDERERS", "PageContext"]
