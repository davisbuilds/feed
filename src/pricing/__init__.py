"""Per-model LLM pricing registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

from src.logging_config import get_logger

logger = get_logger("pricing")

_DATA_DIR = Path(__file__).parent / "data"


class ModelPricing(NamedTuple):
    """Per-million-token pricing for a model."""

    input_cost_per_mtok: float
    output_cost_per_mtok: float


# model name/alias -> ModelPricing
_REGISTRY: dict[str, ModelPricing] = {}


def _load() -> None:
    """Load all JSON pricing files from the data directory."""
    for path in _DATA_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        for model_name, info in data.get("models", {}).items():
            pricing = ModelPricing(
                input_cost_per_mtok=info["inputCostPerMTok"],
                output_cost_per_mtok=info["outputCostPerMTok"],
            )
            _REGISTRY[model_name] = pricing
            for alias in info.get("aliases", []):
                _REGISTRY[alias] = pricing


_load()


def lookup(model: str) -> ModelPricing | None:
    """Look up pricing for a model by canonical name or alias."""
    return _REGISTRY.get(model)


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> float | None:
    """Calculate USD cost for a model invocation. Returns None if model unknown."""
    pricing = lookup(model)
    if pricing is None:
        logger.warning(f"No pricing data for model '{model}'")
        return None
    return (
        (input_tokens / 1_000_000) * pricing.input_cost_per_mtok
        + (output_tokens / 1_000_000) * pricing.output_cost_per_mtok
    )
