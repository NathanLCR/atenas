"""Policy checks for safe Atenas action execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.schemas import ActionOutcome, ActionProposal, ActionTier

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
        "update_memory",
        "clear_work_schedule",
        "remove_assignment",
        "delete_modules",
        "deduplicate_modules",
        "change_config",
        "send_external_message",
        "archive_plan",
        "archive_note",
        "web_search",
    }
)

# Default-deny: only action types listed here (or in CONFIRMATION_REQUIRED,
# once confirmed) may execute. Anything not explicitly allowed is blocked,
# so an LLM cannot bypass policy by inventing a new action_type string.
ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {
        "read_memory",
        "write_memory",
        "search",
        "summarize",
        "add_work_shift",
        "add_class_session",
        "add_assignment",
        "add_note",
        "add_task",
        "set_assignment_status",
        "set_assignment_hours",
        "generate_plan",
        "generate_flashcards",
        "update_matrix",
        "ingest_paper",
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
        elif proposal.action_tier == ActionTier.FORBIDDEN:
            decision = PolicyDecision(
                allowed=False,
                outcome=ActionOutcome.BLOCKED,
                reason=f"Forbidden action tier for: {proposal.action_type}",
            )
        elif (
            proposal.action_type not in ALLOWED_ACTIONS
            and proposal.action_type not in CONFIRMATION_REQUIRED
        ):
            decision = PolicyDecision(
                allowed=False,
                outcome=ActionOutcome.BLOCKED,
                reason=f"Unknown action type (not in allowlist): {proposal.action_type}",
            )
        elif proposal.action_type in CONFIRMATION_REQUIRED or proposal.approval_required:
            if proposal.user_confirmed:
                decision = PolicyDecision(
                    allowed=True,
                    outcome=ActionOutcome.SUCCESS,
                    reason=f"Confirmed by user: {proposal.action_type}",
                )
            else:
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
                "actor_user_id": proposal.payload.get("actor_user_id"),
                "allowed": decision.allowed,
                "outcome": decision.outcome.value,
                "reason": decision.reason,
            },
        )
        return decision
