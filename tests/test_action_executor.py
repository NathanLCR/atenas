"""Tests for policy-checked action execution."""

import logging

from core.action_executor import ActionExecutor
from core.schemas import ActionOutcome, ActionProposal


def proposal(action_type: str, user_confirmed: bool = False) -> ActionProposal:
    """Build a minimal action proposal."""

    return ActionProposal(
        action_type=action_type,
        payload={"value": 1},
        confidence=0.9,
        user_confirmed=user_confirmed,
    )


def test_execute_forbidden_action_is_blocked() -> None:
    """Forbidden actions should be blocked before handler lookup."""

    executor = ActionExecutor()

    result = executor.execute(proposal("shell_exec"))

    assert result.outcome == ActionOutcome.BLOCKED
    assert result.success is False


def test_execute_with_registered_handler_succeeds() -> None:
    """Registered handlers should execute and return success."""

    executor = ActionExecutor()
    executor.register_action("write_memory", lambda payload: {"stored": payload["value"]})

    result = executor.execute(proposal("write_memory"))

    assert result.outcome == ActionOutcome.SUCCESS
    assert result.payload == {"stored": 1}


def test_execute_with_no_handler_returns_error() -> None:
    """Allowed actions without handlers should return an error result."""

    executor = ActionExecutor()

    result = executor.execute(proposal("write_memory"))

    assert result.outcome == ActionOutcome.ERROR
    assert "No handler registered" in result.message


def test_handler_exception_is_caught() -> None:
    """Handler exceptions should not crash the executor."""

    executor = ActionExecutor()

    def failing_handler(payload: dict[str, int]) -> str:
        raise RuntimeError("boom")

    executor.register_action("write_memory", failing_handler)

    result = executor.execute(proposal("write_memory"))

    assert result.outcome == ActionOutcome.ERROR
    assert "boom" in result.message


def test_action_audit_includes_policy_and_payload_summary(
    caplog,
) -> None:
    """Execution audit should include actor, policy decision, outcome, and summary."""

    executor = ActionExecutor()
    executor.register_action("write_memory", lambda payload: "stored")
    caplog.set_level(logging.INFO, logger="core.action_executor")

    result = executor.execute(
        ActionProposal(
            action_type="write_memory",
            payload={"actor_user_id": 123, "body": "sensitive-ish note body"},
            confidence=0.9,
            user_confirmed=True,
        )
    )

    assert result.success is True
    audit = [record for record in caplog.records if record.message == "action_executed"][-1]
    assert audit.actor_user_id == 123
    assert audit.policy_allowed is True
    assert audit.policy_outcome == "success"
    assert audit.outcome == "success"
    assert audit.payload_summary["body"] == "<23 chars>"
