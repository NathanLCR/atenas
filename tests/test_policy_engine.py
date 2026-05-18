"""Tests for policy enforcement."""

import pytest

from core.policy_engine import (
    ALLOWED_ACTIONS,
    CONFIRMATION_REQUIRED,
    FORBIDDEN_ACTIONS,
    PolicyEngine,
)
from core.schemas import ActionOutcome, ActionProposal


def proposal(action_type: str, user_confirmed: bool = False) -> ActionProposal:
    """Build a minimal action proposal for policy tests."""

    return ActionProposal(
        action_type=action_type,
        payload={},
        confidence=0.9,
        user_confirmed=user_confirmed,
    )


@pytest.mark.parametrize("action_type", sorted(FORBIDDEN_ACTIONS))
def test_forbidden_actions_are_blocked(action_type: str) -> None:
    """Every forbidden action should be blocked unconditionally."""

    decision = PolicyEngine().check(proposal(action_type, user_confirmed=True))

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

    decision = PolicyEngine().check(proposal(action_type, user_confirmed=True))

    assert decision.allowed is True
    assert decision.outcome == ActionOutcome.SUCCESS


@pytest.mark.parametrize("action_type", sorted(ALLOWED_ACTIONS))
def test_allowlisted_actions_pass(action_type: str) -> None:
    """Every allowlisted action should pass without confirmation."""

    decision = PolicyEngine().check(proposal(action_type))

    assert decision.allowed is True
    assert decision.outcome == ActionOutcome.SUCCESS


def test_unknown_action_is_blocked_by_default_deny() -> None:
    """Actions not in any policy set must be blocked, not allowed."""

    decision = PolicyEngine().check(proposal("definitely_not_a_real_action"))

    assert decision.allowed is False
    assert decision.outcome == ActionOutcome.BLOCKED


def test_unknown_action_cannot_be_bypassed_by_confirmation() -> None:
    """user_confirmed must not turn an unknown action into an allowed one."""

    decision = PolicyEngine().check(
        proposal("rm_rf_everything", user_confirmed=True)
    )

    assert decision.allowed is False
    assert decision.outcome == ActionOutcome.BLOCKED

