"""Dedicated research pages. Each module exposes ``render(ctx, render_section)``."""

from dashboard.sections import (
    banks,
    consumer,
    demand,
    failure_candidates,
    fc_data,
    financing,
    housing,
    momentum,
    recession,
    sp_relative,
    supply,
    valuation,
    vix_options,
)
from dashboard.sections.common import PageContext

RENDERERS = {
    "Momentum": momentum.render,
    "FC Data": fc_data.render,
    "Failure Candidates": failure_candidates.render,
    "S&P Relative": sp_relative.render,
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
