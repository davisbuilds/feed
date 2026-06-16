"""Tests for model pricing lookup and cost estimates."""

from feed import pricing


def test_lookup_supports_aliases() -> None:
    """Model aliases should resolve to the same pricing as canonical names."""
    canonical = pricing.lookup("claude-opus-4-5-20251101")
    alias = pricing.lookup("claude-opus-4-5")

    assert canonical == alias
    assert canonical == pricing.ModelPricing(input_cost_per_mtok=5, output_cost_per_mtok=25)


def test_estimate_cost_uses_per_million_token_rates() -> None:
    """Cost estimates should combine input and output token rates."""
    cost = pricing.estimate_cost("gpt-5-mini", input_tokens=2_000_000, output_tokens=500_000)

    assert cost == 1.5


def test_estimate_cost_returns_none_for_unknown_model() -> None:
    """Unknown models should not produce a misleading cost estimate."""
    assert pricing.estimate_cost("unknown-model", input_tokens=100, output_tokens=100) is None
