"""Action handler registry and policy-checked execution."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from core.policy_engine import PolicyDecision, PolicyEngine
from core.schemas import ActionOutcome, ActionProposal, ActionResult

logger = logging.getLogger(__name__)
ActionHandler = Callable[[dict[str, Any]], ActionResult | dict[str, Any] | str | None]


class ActionExecutor:
    """Execute registered action handlers after policy approval."""

    def __init__(self, policy_engine: PolicyEngine | None = None) -> None:
        self.policy_engine = policy_engine or PolicyEngine()
        self._handlers: dict[str, ActionHandler] = {}

    def register_action(self, action_type: str, handler: ActionHandler) -> None:
        """Register a handler for an action type."""

        self._handlers[action_type] = handler
        logger.info(
            "action_registered",
            extra={"event_type": "action_registered", "action_type": action_type},
        )

    def execute(self, proposal: ActionProposal) -> ActionResult:
        """Execute an action proposal if policy and handler lookup pass."""

        decision = self.policy_engine.check(proposal)
        if not decision.allowed:
            result = ActionResult(
                action_type=proposal.action_type,
                outcome=decision.outcome,
                message=decision.reason,
            )
            self._log_execution(proposal, result, decision)
            return result

        handler = self._handlers.get(proposal.action_type)
        if handler is None:
            result = ActionResult(
                action_type=proposal.action_type,
                outcome=ActionOutcome.ERROR,
                message=f"No handler registered for action: {proposal.action_type}",
            )
            self._log_execution(proposal, result, decision)
            return result

        try:
            if inspect.iscoroutinefunction(handler):
                raise RuntimeError(
                    f"Async action handler '{proposal.action_type}' is not supported. "
                    "Register a synchronous handler instead."
                )
            handler_result = handler(proposal.payload)
            result = self._normalize_result(proposal.action_type, handler_result)
        except Exception as exc:
            logger.exception(
                "action_handler_exception",
                extra={
                    "event_type": "action_handler_exception",
                    "action_type": proposal.action_type,
                },
            )
            result = ActionResult(
                action_type=proposal.action_type,
                outcome=ActionOutcome.ERROR,
                message=f"Handler failed: {exc}",
            )

        self._log_execution(proposal, result, decision)
        return result

    def _normalize_result(
        self,
        action_type: str,
        handler_result: ActionResult | dict[str, Any] | str | None,
    ) -> ActionResult:
        """Convert handler return values into an ActionResult."""

        if isinstance(handler_result, ActionResult):
            return handler_result
        if isinstance(handler_result, dict):
            return ActionResult(
                action_type=action_type,
                outcome=ActionOutcome.SUCCESS,
                message="Action executed successfully.",
                payload=handler_result,
            )
        if isinstance(handler_result, str):
            return ActionResult(
                action_type=action_type,
                outcome=ActionOutcome.SUCCESS,
                message=handler_result,
            )
        return ActionResult(
            action_type=action_type,
            outcome=ActionOutcome.SUCCESS,
            message="Action executed successfully.",
        )

    def _log_execution(
        self,
        proposal: ActionProposal,
        result: ActionResult,
        decision: PolicyDecision,
    ) -> None:
        """Log every action execution attempt."""

        logger.info(
            "action_executed",
            extra={
                "event_type": "action_executed",
                "action_type": proposal.action_type,
                "actor_user_id": proposal.payload.get("actor_user_id"),
                "confidence": proposal.confidence,
                "origin": proposal.origin.value,
                "criticality": proposal.criticality.value,
                "approval_required": proposal.approval_required,
                "policy_allowed": decision.allowed,
                "policy_outcome": decision.outcome.value,
                "policy_reason": decision.reason,
                "outcome": result.outcome.value,
                "success": result.success,
                "user_confirmed": proposal.user_confirmed,
                "payload_summary": _payload_summary(proposal.payload),
            },
        )


_executor = ActionExecutor()


def register_action(action_type: str, handler: ActionHandler) -> None:
    """Register an action handler on the process-wide executor."""

    _executor.register_action(action_type, handler)


def execute(proposal: ActionProposal) -> ActionResult:
    """Execute an action proposal on the process-wide executor."""

    return _executor.execute(proposal)


def _payload_summary(payload: dict[str, Any], max_length: int = 280) -> dict[str, Any]:
    """Return a compact, non-secret payload summary for action audit logs."""

    redacted_keys = {"body", "content", "notes", "token", "secret", "password"}
    summary: dict[str, Any] = {}
    for key in sorted(payload):
        value = payload[key]
        if key in redacted_keys and isinstance(value, str):
            summary[key] = f"<{len(value)} chars>"
        elif isinstance(value, str) and len(value) > max_length:
            summary[key] = value[:max_length].rstrip() + "..."
        elif isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value
        elif isinstance(value, list):
            summary[key] = f"<list:{len(value)}>"
        elif isinstance(value, dict):
            summary[key] = f"<dict:{len(value)}>"
        else:
            summary[key] = str(value)
    return summary
