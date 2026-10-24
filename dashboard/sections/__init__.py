"""Dedicated research pages. Each module exposes ``render(ctx, render_section)``."""

from dashboard.sections import banks, consumer, housing, valuation
from dashboard.sections.common import PageContext

RENDERERS = {
    "Housing": housing.render,
    "Banks": banks.render,
    "Valuation": valuation.render,
    "Consumer": consumer.render,
}

__all__ = ["RENDERERS", "PageContext"]
