"""Local model capability profiles and definitions."""

from __future__ import annotations

from core.schemas import StrictModel


class ModelProfile(StrictModel):
    """Local model capability profile."""

    name: str
    context_window_tokens: int = 8192
    prompt_token_budget: int = 4096
    timeout_seconds: int = 60
    max_history_items: int = 8
    max_tools_per_turn: int = 30
    max_turn_iterations: int = 5
    strict_json: bool = False
    temperature: float = 0.0


CONSERVATIVE_PROFILE = ModelProfile(
    name="conservative",
    context_window_tokens=8192,
    prompt_token_budget=4096,
    timeout_seconds=60,
    max_history_items=8,
    max_tools_per_turn=30,
    max_turn_iterations=5,
    strict_json=False,
    temperature=0.0,
)


def get_profile(name: str = "conservative") -> ModelProfile:
    """Return a model profile by name."""
    if name == "conservative":
        return CONSERVATIVE_PROFILE
    # Fall back to conservative for unknown names
    return CONSERVATIVE_PROFILE
