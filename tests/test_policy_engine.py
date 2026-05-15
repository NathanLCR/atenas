"""Tests for policy enforcement."""

import pytest

from core.policy_engine import CONFIRMATION_REQUIRED, FORBIDDEN_ACTIONS, PolicyEngine
from core.schemas import ActionOutcome, ActionProposal


def proposal(action_type: str, requires_confirmation: bool = False) -> ActionProposal:
    """Build a minimal action proposal for policy tests."""

    return ActionProposal(
        action_type=action_type,
        payload={},
        confidence=0.9,
        requires_confirmation=requires_confirmation,
    )


@pytest.mark.parametrize("action_type", sorted(FORBIDDEN_ACTIONS))
def test_forbidden_actions_are_blocked(action_type: str) -> None:
    """Every forbidden action should be blocked unconditionally."""

    decision = PolicyEngine().check(proposal(action_type, requires_confirmation=True))

    assert decision.allowed is False
    assert decision.outcome == ActionOutcome.BLOCKED


@pytest.mark.parametrize("action_type", sorted(CONFIRMATION_REQUIRED))
def test_confirmation_required_actions_without_confirmation_are_blocked(
    action_type: str,
) -> None:
    """Every confirmation-required action should be blocked without confirmation."""

    decision = PolicyEngine().check(proposal(action_type))

    assert decision.allowed is False
    assert decision.outcome == ActionOutcome.NEEDS_CONFIRMATION


@pytest.mark.parametrize("action_type", sorted(CONFIRMATION_REQUIRED))
def test_confirmation_required_actions_with_confirmation_are_allowed(
    action_type: str,
) -> None:
    """Confirmation-required actions should pass with explicit confirmation."""

    decision = PolicyEngine().check(proposal(action_type, requires_confirmation=True))

    assert decision.allowed is True
    assert decision.outcome == ActionOutcome.SUCCESS


def test_allowed_action_passes() -> None:
    """Normal allowed actions should pass."""

    decision = PolicyEngine().check(proposal("write_memory"))

    assert decision.allowed is True
    assert decision.outcome == ActionOutcome.SUCCESS

