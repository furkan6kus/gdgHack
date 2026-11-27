"""Rough cost estimate from token usage."""

from __future__ import annotations

from mytool.core.models import TokenUsage

# USD per 1M tokens as (input, output). A snapshot: prices change, so treat the
# result as an estimate and update this table when the provider's list changes.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-2": (8.00, 40.00),
}


def estimate_cost(model: str, usage: TokenUsage) -> float | None:
    """Estimated USD cost, or None when the model is not in the price table."""
    price = PRICES_PER_MTOK.get(model)
    if price is None:
        return None
    input_price, output_price = price
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000
