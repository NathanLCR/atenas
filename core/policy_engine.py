"""Policy checks for safe Atenas action execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.schemas import ActionOutcome, ActionProposal

logger = logging.getLogger(__name__)

FORBIDDEN_ACTIONS: frozenset[str] = frozenset(
    {
        "shell_exec",
        "modify_source_code",
        "edit_env_file",
        "read_ssh_keys",
        "read_credentials",
        "install_package",
        "delete_file_silent",
        "change_permissions",
        "unrestricted_fs_access",
        "send_external_message_without_consent",
    }
)

CONFIRMATION_REQUIRED: frozenset[str] = frozenset(
    {
        "delete_file",
        "overwrite_memory",
        "clear_work_schedule",
        "remove_assignment",
        "change_config",
        "send_external_message",
        "archive_plan",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    """Decision returned by the policy engine."""

    allowed: bool
    outcome: ActionOutcome
    reason: str


class PolicyEngine:
    """Stateless policy engine for action proposals."""

    def check(self, proposal: ActionProposal) -> PolicyDecision:
        """Return whether an action proposal is allowed."""

        if proposal.action_type in FORBIDDEN_ACTIONS:
            decision = PolicyDecision(
                allowed=False,
                outcome=ActionOutcome.BLOCKED,
                reason=f"Forbidden action: {proposal.action_type}",
            )
        elif (
            proposal.action_type in CONFIRMATION_REQUIRED
            and not proposal.requires_confirmation
        ):
            decision = PolicyDecision(
                allowed=False,
                outcome=ActionOutcome.NEEDS_CONFIRMATION,
                reason=f"Action requires explicit confirmation: {proposal.action_type}",
            )
        else:
            decision = PolicyDecision(
                allowed=True,
                outcome=ActionOutcome.SUCCESS,
                reason="Action allowed by policy.",
            )

        logger.info(
            "policy_decision",
            extra={
                "event_type": "policy_decision",
                "action_type": proposal.action_type,
                "allowed": decision.allowed,
                "outcome": decision.outcome.value,
                "reason": decision.reason,
            },
        )
        return decision

