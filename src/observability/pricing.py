"""Model pricing for cost tracking (Phase 6).

Prices are expressed in USD per 1M tokens as ``(input, output)``. Model
matching is by case-insensitive keyword: the longest matching keyword wins,
so ``gpt-4o-mini`` is matched before ``gpt-4o``. Unknown models report a
cost of ``0.0`` rather than failing.
"""

from __future__ import annotations

# Model keyword -> (input, output) USD per 1M tokens.
# Sorted by keyword length at lookup time so more specific names win.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1": (2.0, 8.0),
    "o4-mini": (1.1, 4.4),
    "o3": (2.0, 8.0),
}


def get_pricing(model: str) -> tuple[float, float] | None:
    """Return ``(input, output)`` USD per 1M tokens for *model*, or None."""
    m = model.lower()
    for keyword in sorted(PRICING, key=len, reverse=True):
        if keyword in m:
            return PRICING[keyword]
    return None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute the USD cost of a single call, or 0.0 for unknown models."""
    pricing = get_pricing(model)
    if pricing is None:
        return 0.0
    input_price, output_price = pricing
    return (input_tokens / 1_000_000) * input_price + (
        output_tokens / 1_000_000
    ) * output_price
