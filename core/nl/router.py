"""Natural language router: maps IntentMatch to existing service/command calls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from core.action_executor import ActionExecutor
from core.academic.service import AcademicService
from core.academic.validators import (
    CommandResult,
    parse_datetime_input,
    parse_datetime_strict,
    parse_weekday,
    validate_energy_cost,
    validate_hours,
    validate_priority,
    validate_status,
    validate_text_field,
)
from core.knowledge.validators import normalize_tags, validate_note_body, validate_note_title
from core.knowledge.service import KnowledgeService
from core.llm.service import LLMService
from core.nl.intent import (
    INTENT_ADD_ASSIGNMENT,
    INTENT_ADD_CLASS,
    INTENT_ADD_NOTE,
    INTENT_ADD_SHIFT,
    INTENT_ARCHIVE_NOTE,
    INTENT_ASK_NOTES,
    INTENT_AVAILABILITY,
    INTENT_DEADLINES,
    INTENT_LIST_ASSIGNMENTS,
    INTENT_LIST_MODULES,
    INTENT_LIST_SHIFTS,
    INTENT_NOTE_ACTION,
    INTENT_PLAN,
    INTENT_REMINDERS,
    INTENT_SET_HOURS,
    INTENT_SET_STATUS,
    INTENT_STUDY,
    INTENT_TODAY,
    INTENT_UNKNOWN,
    INTENT_WEEK,
    READ_INTENTS,
    IntentMatch,
)
from core.notifications.service import NotificationService
from core.retrieval.service import RetrievalService
from core.schemas import (
    ActionCriticality,
    ActionOrigin,
    ActionOutcome,
    ActionProposal,
    ActionResult,
)
from core.time import parse_hhmm

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

ACTION_SET_ASSIGNMENT_STATUS = "set_assignment_status"
ACTION_SET_ASSIGNMENT_HOURS = "set_assignment_hours"
ACTION_ADD_CLASS_SESSION = "add_class_session"
ACTION_ADD_WORK_SHIFT = "add_work_shift"
ACTION_ADD_NOTE = "add_note"
ACTION_ARCHIVE_NOTE = "archive_note"
ACTOR_PAYLOAD_KEY = "actor_user_id"

PRIORITY_LABELS: dict[str, int] = {
    "low": 1,
    "medium": 3,
    "normal": 3,
    "high": 5,
    "critical": 5,
    "urgent": 5,
}

SLASH_COMMAND_SUGGESTIONS: dict[str, str] = {
    INTENT_TODAY: "/today",
    INTENT_WEEK: "/week",
    INTENT_DEADLINES: "/deadlines",
    INTENT_AVAILABILITY: "/availability",
    INTENT_PLAN: "/plan",
    INTENT_STUDY: "/study",
    INTENT_ADD_ASSIGNMENT: "/add_assignment",
    INTENT_SET_STATUS: "/set_status",
    INTENT_SET_HOURS: "/set_hours",
    INTENT_ADD_CLASS: "/add_class",
    INTENT_ADD_SHIFT: "/add_shift",
    INTENT_LIST_ASSIGNMENTS: "/assignments",
    INTENT_LIST_MODULES: "/modules",
    INTENT_LIST_SHIFTS: "/shifts",
    INTENT_ADD_NOTE: "/add_note",
    INTENT_ARCHIVE_NOTE: "/archive_note",
    INTENT_NOTE_ACTION: "/summarize_note or /explain_note",
    INTENT_ASK_NOTES: "/ask_notes",
    INTENT_REMINDERS: "/reminders",
}


class NLProposalError(ValueError):
    """Raised when a natural-language write cannot become a safe proposal."""


class NLRouter:
    """Routes classified intents to existing service calls."""

    def __init__(
        self,
        db_path: Path,
        timezone: str = "Europe/Dublin",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1:8b",
        ollama_timeout: int = 60,
        action_executor: ActionExecutor | None = None,
    ) -> None:
        self._db_path = db_path
        self._tz = timezone
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._ollama_timeout = ollama_timeout
        self._action_executor = action_executor or ActionExecutor()
        self._register_write_handlers()

    def route_read(self, match: IntentMatch) -> str:
        """Execute a read intent and return the response text."""
        if match.intent == INTENT_TODAY:
            return self._today()
        if match.intent == INTENT_WEEK:
            return self._week()
        if match.intent == INTENT_DEADLINES:
            return self._deadlines()
        if match.intent == INTENT_AVAILABILITY:
            return self._availability()
        if match.intent == INTENT_PLAN:
            return self._plan()
        if match.intent == INTENT_STUDY:
            return self._study()
        if match.intent == INTENT_LIST_ASSIGNMENTS:
            return self._list_assignments()
        if match.intent == INTENT_LIST_MODULES:
            return self._list_modules()
        if match.intent == INTENT_LIST_SHIFTS:
            return self._list_shifts()
        if match.intent == INTENT_NOTE_ACTION:
            return self._note_action(match.slots)
        if match.intent == INTENT_ASK_NOTES:
            return self._ask_notes(match.slots)
        if match.intent == INTENT_REMINDERS:
            return self._reminders()
        return self._fallback(match)

    def build_write_proposal(
        self,
        match: IntentMatch,
        *,
        actor_user_id: int | None,
    ) -> ActionProposal:
        """Validate a write intent into a pending action proposal.

        This is the mutation boundary: the LLM/classifier may suggest slots,
        but code authors the ActionProposal and leaves user_confirmed false.
        """

        if match.intent == INTENT_ADD_ASSIGNMENT:
            action_type = INTENT_ADD_ASSIGNMENT
            payload = self._payload_add_assignment(match.slots)
        elif match.intent == INTENT_SET_STATUS:
            action_type = ACTION_SET_ASSIGNMENT_STATUS
            payload = self._payload_set_status(match.slots)
        elif match.intent == INTENT_SET_HOURS:
            action_type = ACTION_SET_ASSIGNMENT_HOURS
            payload = self._payload_set_hours(match.slots)
        elif match.intent == INTENT_ADD_CLASS:
            action_type = ACTION_ADD_CLASS_SESSION
            payload = self._payload_add_class(match.slots)
        elif match.intent == INTENT_ADD_SHIFT:
            action_type = ACTION_ADD_WORK_SHIFT
            payload = self._payload_add_shift(match.slots)
        elif match.intent == INTENT_ADD_NOTE:
            action_type = ACTION_ADD_NOTE
            payload = self._payload_add_note(match.slots)
        elif match.intent == INTENT_ARCHIVE_NOTE:
            action_type = ACTION_ARCHIVE_NOTE
            payload = self._payload_archive_note(match.slots)
        else:
            raise NLProposalError("I'm not sure what to do. Try /help.")

        if actor_user_id is not None:
            payload[ACTOR_PAYLOAD_KEY] = actor_user_id

        return ActionProposal(
            action_type=action_type,
            payload=payload,
            confidence=match.confidence,
            user_confirmed=False,
            origin=ActionOrigin.TELEGRAM_NL,
            criticality=(
                ActionCriticality.DESTRUCTIVE
                if action_type == ACTION_ARCHIVE_NOTE
                else ActionCriticality.LOCAL_WRITE
            ),
            reason=f"Telegram natural-language intent: {match.intent}",
        )

    def build_confirmation(self, pending: IntentMatch | ActionProposal) -> str:
        """Build a confirmation message for a write intent."""
        proposal = self._coerce_pending_proposal(pending, actor_user_id=None)
        if proposal.action_type == INTENT_ADD_ASSIGNMENT:
            return self._confirm_add_assignment(proposal.payload)
        if proposal.action_type == ACTION_SET_ASSIGNMENT_STATUS:
            return self._confirm_set_status(proposal.payload)
        if proposal.action_type == ACTION_SET_ASSIGNMENT_HOURS:
            return self._confirm_set_hours(proposal.payload)
        if proposal.action_type == ACTION_ADD_CLASS_SESSION:
            return self._confirm_add_class(proposal.payload)
        if proposal.action_type == ACTION_ADD_WORK_SHIFT:
            return self._confirm_add_shift(proposal.payload)
        if proposal.action_type == ACTION_ADD_NOTE:
            return self._confirm_add_note(proposal.payload)
        if proposal.action_type == ACTION_ARCHIVE_NOTE:
            return self._confirm_archive_note(proposal.payload)
        return "I'm not sure what to do. Try /help."

    def execute_write(self, match: IntentMatch) -> str:
        """Refuse direct write execution without an explicit confirmation step."""

        return 'Write intent requires explicit confirmation. Reply "yes" to confirm first.'

    def execute_confirmed_write(
        self,
        pending: IntentMatch | ActionProposal,
        *,
        actor_user_id: int | None,
    ) -> str:
        """Mark a pending proposal confirmed and execute via ActionExecutor."""

        try:
            proposal = self._coerce_pending_proposal(pending, actor_user_id=actor_user_id)
        except NLProposalError as exc:
            return str(exc)

        proposal_actor = proposal.payload.get(ACTOR_PAYLOAD_KEY)
        if (
            actor_user_id is not None
            and proposal_actor is not None
            and proposal_actor != actor_user_id
        ):
            return "Confirmation cancelled because the Telegram user changed."

        payload = dict(proposal.payload)
        if actor_user_id is not None:
            payload[ACTOR_PAYLOAD_KEY] = actor_user_id
        confirmed = proposal.model_copy(
            update={"payload": payload, "user_confirmed": True}
        )
        result = self._action_executor.execute(confirmed)
        return result.message

    def suggest_command(self, match: IntentMatch) -> str:
        """Suggest the closest slash command for an unclear intent."""
        cmd = SLASH_COMMAND_SUGGESTIONS.get(match.intent)
        if cmd:
            return f"I'm not entirely sure what you mean. Try: {cmd}"
        return f"I didn't understand that. You can try /ask_notes with your question, or use /status to see available commands."

    def _register_write_handlers(self) -> None:
        """Register NL write handlers on this router's policy executor."""

        self._action_executor.register_action(INTENT_ADD_ASSIGNMENT, self._handle_add_assignment)
        self._action_executor.register_action(
            ACTION_SET_ASSIGNMENT_STATUS,
            self._handle_set_assignment_status,
        )
        self._action_executor.register_action(
            ACTION_SET_ASSIGNMENT_HOURS,
            self._handle_set_assignment_hours,
        )
        self._action_executor.register_action(ACTION_ADD_CLASS_SESSION, self._handle_add_class)
        self._action_executor.register_action(ACTION_ADD_WORK_SHIFT, self._handle_add_shift)
        self._action_executor.register_action(ACTION_ADD_NOTE, self._handle_add_note)
        self._action_executor.register_action(ACTION_ARCHIVE_NOTE, self._handle_archive_note)

    def _coerce_pending_proposal(
        self,
        pending: IntentMatch | ActionProposal,
        *,
        actor_user_id: int | None,
    ) -> ActionProposal:
        """Restore older pending shapes into the current ActionProposal form."""

        if isinstance(pending, ActionProposal):
            return pending
        if isinstance(pending, IntentMatch):
            return self.build_write_proposal(pending, actor_user_id=actor_user_id)
        raise NLProposalError("Pending action could not be restored. Please try again.")

    def _payload_add_assignment(self, slots: dict[str, str]) -> dict[str, Any]:
        title = self._required_slot(slots, "title", label="assignment title")
        title = self._validate_short_text(title, label="Assignment title")
        due = self._required_slot(slots, "due_at", "due", label="due date")
        due = self._parse_due_at(due)
        payload: dict[str, Any] = {
            "title": title,
            "due_at": due,
            "priority": self._parse_priority(slots.get("priority")),
        }
        module_id = self._optional_slot(slots, "module_id", "module")
        if module_id:
            resolved_module_id, module_name = self._resolve_module_id(module_id)
            payload["module_id"] = resolved_module_id
            payload["module_name"] = module_name
        estimated_hours = self._parse_estimated_hours(slots.get("estimated_hours"))
        if estimated_hours is not None:
            payload["estimated_hours"] = estimated_hours
        notes = self._optional_slot(slots, "notes")
        if notes:
            payload["notes"] = notes
        return payload

    def _payload_set_status(self, slots: dict[str, str]) -> dict[str, Any]:
        assignment = self._required_slot(
            slots,
            "assignment_id",
            "assignment_id_or_title",
            "assignment",
            label="assignment",
        )
        status = self._required_slot(slots, "status", label="status").lower()
        validated_status = validate_status(status)
        if validated_status is None:
            raise NLProposalError("Invalid status. Use todo, in_progress, submitted, done, or cancelled.")

        assignment_id, assignment_title = self._resolve_assignment_id(assignment)
        return {
            "assignment_id": assignment_id,
            "assignment_title": assignment_title,
            "status": validated_status,
        }

    def _payload_set_hours(self, slots: dict[str, str]) -> dict[str, Any]:
        assignment = self._required_slot(
            slots,
            "assignment_id",
            "assignment_id_or_title",
            "assignment",
            label="assignment",
        )
        completed = self._required_slot(
            slots,
            "completed_hours",
            "completed",
            "hours",
            label="completed hours",
        )
        completed_hours = validate_hours(completed)
        if completed_hours is None:
            raise NLProposalError("Completed hours must be between 0 and 1000.")
        assignment_id, assignment_title = self._resolve_assignment_id(assignment)
        return {
            "assignment_id": assignment_id,
            "assignment_title": assignment_title,
            "completed_hours": completed_hours,
        }

    def _payload_add_class(self, slots: dict[str, str]) -> dict[str, Any]:
        title = self._required_slot(slots, "title", label="class title")
        title = self._validate_short_text(title, label="Class title")
        day = self._required_slot(slots, "day", "weekday", label="weekday")
        weekday = parse_weekday(day)
        if weekday is None:
            raise NLProposalError("Invalid weekday. Use 0-6 or mon/tue/wed/thu/fri/sat/sun.")
        start_time = self._required_slot(slots, "start_time", "start", label="start time")
        end_time = self._required_slot(slots, "end_time", "end", label="end time")
        start_clock = self._parse_hhmm(start_time, label="start_time")
        end_clock = self._parse_hhmm(end_time, label="end_time")
        if start_clock >= end_clock:
            raise NLProposalError("start_time must be before end_time.")

        payload: dict[str, Any] = {
            "title": title,
            "weekday": weekday,
            "start_time": start_clock.strftime("%H:%M"),
            "end_time": end_clock.strftime("%H:%M"),
        }
        module_id = self._optional_slot(slots, "module_id", "module")
        if module_id:
            resolved_module_id, module_name = self._resolve_module_id(module_id)
            payload["module_id"] = resolved_module_id
            payload["module_name"] = module_name
        location = self._optional_slot(slots, "location")
        if location:
            payload["location"] = self._validate_short_text(location, label="Location")
        notes = self._optional_slot(slots, "notes")
        if notes:
            payload["notes"] = notes
        return payload

    def _payload_add_shift(self, slots: dict[str, str]) -> dict[str, Any]:
        start = self._required_slot(slots, "start_at", "start", label="shift start")
        end = self._required_slot(slots, "end_at", "end", label="shift end")
        start_at = self._parse_shift_datetime(start, label="start_at")
        end_at = self._parse_shift_datetime(end, label="end_at")
        if start_at >= end_at:
            raise NLProposalError("start_at must be before end_at.")

        title = self._optional_slot(slots, "title") or "Work"
        payload: dict[str, Any] = {
            "title": self._validate_short_text(title, label="Shift title"),
            "start_at": start_at.strftime("%Y-%m-%d %H:%M"),
            "end_at": end_at.strftime("%Y-%m-%d %H:%M"),
        }
        location = self._optional_slot(slots, "location")
        if location:
            payload["location"] = self._validate_short_text(location, label="Location")
        role = self._optional_slot(slots, "role")
        if role:
            payload["role"] = self._validate_short_text(role, label="Role")
        energy = self._optional_slot(slots, "energy_cost", "energy")
        if energy:
            energy_cost = validate_energy_cost(energy)
            if energy_cost is None:
                raise NLProposalError("Energy cost must be between 1 and 5.")
            payload["energy_cost"] = energy_cost
        notes = self._optional_slot(slots, "notes")
        if notes:
            payload["notes"] = notes
        return payload

    def _payload_add_note(self, slots: dict[str, str]) -> dict[str, Any]:
        title = self._required_slot(slots, "title", label="note title")
        title = self._validate_note_title(title)
        body = self._required_slot(slots, "content", "body", label="note body")
        body = self._validate_note_body(body)
        payload: dict[str, Any] = {"title": title, "body": body}
        module_id = self._optional_slot(slots, "module_id", "module")
        if module_id:
            resolved_module_id, module_name = self._resolve_module_id(module_id)
            payload["module_id"] = resolved_module_id
            payload["module_name"] = module_name
        assignment_id = self._optional_slot(slots, "assignment_id", "assignment")
        if assignment_id:
            resolved_assignment_id, assignment_title = self._resolve_assignment_id(assignment_id)
            payload["assignment_id"] = resolved_assignment_id
            payload["assignment_title"] = assignment_title
        tags = self._parse_tags(slots.get("tags"))
        if tags:
            payload["tags"] = tags
        return payload

    def _payload_archive_note(self, slots: dict[str, str]) -> dict[str, Any]:
        note_id_str = self._required_slot(slots, "note_id", "id", label="note ID")
        try:
            note_id = int(note_id_str)
        except ValueError as exc:
            raise NLProposalError(f"Invalid note ID: {note_id_str}") from exc
        note = self._build_knowledge_service().get_note(note_id)
        if note is None:
            raise NLProposalError(f"Note #{note_id} not found.")
        if note.archived:
            raise NLProposalError(f"Note #{note_id} is already archived.")
        return {"note_id": note_id, "note_title": note.title}

    def _required_slot(self, slots: dict[str, str], *names: str, label: str) -> str:
        value = self._optional_slot(slots, *names)
        if value is None:
            raise NLProposalError(f"Missing {label}.")
        return value

    def _optional_slot(self, slots: dict[str, str], *names: str) -> str | None:
        for name in names:
            value = slots.get(name)
            if value is None:
                continue
            trimmed = str(value).strip()
            if trimmed:
                return trimmed
        return None

    def _parse_priority(self, value: str | None) -> int:
        if value is None:
            return 3
        normalized = value.strip().lower()
        if normalized in PRIORITY_LABELS:
            return PRIORITY_LABELS[normalized]
        priority = validate_priority(normalized)
        if priority is None:
            raise NLProposalError("Priority must be between 1 and 5.")
        return priority

    def _parse_estimated_hours(self, value: str | None) -> float | None:
        if value is None or not str(value).strip():
            return None
        hours = validate_hours(value)
        if hours is None:
            raise NLProposalError("Estimated hours must be between 0 and 1000.")
        return hours

    def _parse_due_at(self, value: str) -> str:
        parsed, error = parse_datetime_input(value, ZoneInfo(self._tz))
        if error:
            raise NLProposalError(error)
        return parsed.strftime("%Y-%m-%d %H:%M")

    def _parse_hhmm(self, value: str, *, label: str):
        try:
            return parse_hhmm(value)
        except ValueError as exc:
            raise NLProposalError(f"{label} must be HH:MM format.") from exc

    def _parse_shift_datetime(self, value: str, *, label: str):
        parsed, error = parse_datetime_strict(value, ZoneInfo(self._tz))
        if error:
            raise NLProposalError(error.replace("datetime", label, 1))
        return parsed

    def _parse_tags(self, value: str | None) -> list[str] | None:
        if value is None:
            return None
        tags = normalize_tags(value)
        return tags or None

    def _validate_short_text(self, value: str, *, label: str) -> str:
        validated = validate_text_field(value, required=True)
        if not validated:
            raise NLProposalError(f"{label} is required.")
        return validated

    def _validate_note_title(self, value: str) -> str:
        validated = validate_note_title(value)
        if not validated:
            raise NLProposalError("Note title is required.")
        return validated

    def _validate_note_body(self, value: str) -> str:
        validated = validate_note_body(value)
        if not validated:
            raise NLProposalError("Note body is required.")
        return validated

    def _resolve_module_id(self, value: str) -> tuple[str, str]:
        service = self._build_academic_service()
        existing = service.repository.get_module_by_id(value)
        if existing is not None:
            return existing.id, existing.name

        lowered = value.casefold()
        matches = [
            module
            for module in service.list_modules()
            if module.name.casefold() == lowered
            or (module.code is not None and module.code.casefold() == lowered)
            or module.id.startswith(value)
        ]
        if len(matches) == 1:
            return matches[0].id, matches[0].name
        if len(matches) > 1:
            raise NLProposalError("Multiple modules match that label. Use the module ID.")
        raise NLProposalError(f"Module not found: {value}")

    def _resolve_assignment_id(self, value: str) -> tuple[str, str]:
        service = self._build_academic_service()
        existing = service.repository.get_assignment_by_id(value)
        if existing is not None:
            return existing.id, existing.title

        matches = [
            assignment
            for assignment in service.list_all_assignments(include_completed=True)
            if assignment.title.casefold() == value.casefold()
            or assignment.id.startswith(value)
        ]
        if len(matches) == 1:
            return matches[0].id, matches[0].title
        if len(matches) > 1:
            raise NLProposalError(
                "Multiple assignments match that title. Use the assignment ID."
            )
        raise NLProposalError(f"Assignment not found: {value}")

    def _build_academic_service(self) -> AcademicService:
        return AcademicService(self._db_path, timezone=self._tz)

    def _build_knowledge_service(self) -> KnowledgeService:
        return KnowledgeService(self._db_path, timezone=self._tz)

    def _build_retrieval_service(self) -> RetrievalService:
        return RetrievalService(
            db_path=self._db_path,
            timezone=self._tz,
            ollama_base_url=self._ollama_base_url,
            ollama_model=self._ollama_model,
            ollama_timeout=self._ollama_timeout,
        )

    def _build_llm_service(self) -> LLMService:
        return LLMService(
            db_path=self._db_path,
            timezone=self._tz,
            ollama_base_url=self._ollama_base_url,
            ollama_model=self._ollama_model,
            ollama_timeout=self._ollama_timeout,
        )

    def _build_notification_service(self) -> NotificationService:
        return NotificationService(db_path=self._db_path, timezone=self._tz)

    def _today(self) -> str:
        service = self._build_academic_service()
        overview = service.get_today_overview()
        return _format_today(overview)

    def _week(self) -> str:
        service = self._build_academic_service()
        overview = service.get_week_overview()
        return _format_week(overview)

    def _deadlines(self) -> str:
        service = self._build_academic_service()
        assignments = service.list_upcoming_assignments(limit=10)
        return _format_deadlines(assignments)

    def _availability(self) -> str:
        service = self._build_academic_service()
        overview = service.get_today_overview()
        return _format_availability(overview.availability)

    def _plan(self) -> str:
        service = self._build_academic_service()
        plan = service.get_study_plan()
        return _format_plan(plan)

    def _study(self) -> str:
        service = self._build_academic_service()
        plan = service.get_study_plan()
        return _format_study_recommendation(
            today_block=service.get_today_study_recommendation(),
            next_block=service.get_next_study_recommendation(),
            plan=plan,
        )

    def _list_assignments(self) -> str:
        service = self._build_academic_service()
        assignments = service.list_all_assignments(include_completed=False)
        return _format_assignments(assignments)

    def _list_modules(self) -> str:
        service = self._build_academic_service()
        modules = service.list_modules()
        return _format_modules(modules)

    def _list_shifts(self) -> str:
        service = self._build_academic_service()
        shifts = service.list_all_work_shifts(limit=30)
        return _format_shifts(shifts)

    def _note_action(self, slots: dict[str, str]) -> str:
        note_id_str = slots.get("note_id")
        action = slots.get("action", "summarize")
        if not note_id_str:
            return "Which note? Please specify a note number, e.g. 'summarise note 5'."
        try:
            note_id = int(note_id_str)
        except ValueError:
            return f"Invalid note ID: {note_id_str}"

        service = self._build_llm_service()
        note = service.knowledge.get_note(note_id)
        title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"

        action_map = {
            "summarize": lambda: service.summarize_note(note_id),
            "explain": lambda: service.explain_note(note_id),
            "questions": lambda: service.generate_questions_from_note(note_id),
            "flashcards": lambda: service.generate_flashcards_from_note(note_id),
            "rewrite": lambda: service.rewrite_note(note_id, style="concise"),
        }
        fn = action_map.get(action, action_map["summarize"])
        result = fn()
        return _format_llm_result(result, title)

    def _ask_notes(self, slots: dict[str, str]) -> str:
        query = slots.get("query", "")
        if not query:
            return "What would you like to search for in your notes?"
        service = self._build_retrieval_service()
        result = service.answer_question(query, max_sources=5)
        return _format_retrieval_answer(result)

    def _reminders(self) -> str:
        service = self._build_notification_service()
        lines = ["Reminders", ""]
        deadline_msg = service.format_deadline_alerts_message(alert_hours=72)
        if deadline_msg:
            lines.append(deadline_msg)
        else:
            lines.append("No deadlines within the next 72h.")
        overdue_msg = service.format_overdue_message()
        if overdue_msg:
            lines.extend(["", overdue_msg])
        return "\n".join(lines)

    def _handle_add_assignment(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_academic_service()
        result = service.add_assignment(
            title=payload["title"],
            due_at=payload["due_at"],
            module_id=payload.get("module_id"),
            priority=payload.get("priority", 3),
            estimated_hours=payload.get("estimated_hours"),
            notes=payload.get("notes"),
        )
        return self._action_result(INTENT_ADD_ASSIGNMENT, result)

    def _handle_set_assignment_status(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_academic_service()
        result = service.update_assignment_status(
            payload["assignment_id"],
            payload["status"],
        )
        return self._action_result(ACTION_SET_ASSIGNMENT_STATUS, result)

    def _handle_set_assignment_hours(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_academic_service()
        result = service.update_completed_hours(
            payload["assignment_id"],
            payload["completed_hours"],
        )
        return self._action_result(ACTION_SET_ASSIGNMENT_HOURS, result)

    def _handle_add_class(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_academic_service()
        result = service.add_class_session(
            title=payload["title"],
            weekday=payload["weekday"],
            start_time=payload["start_time"],
            end_time=payload["end_time"],
            module_id=payload.get("module_id"),
            location=payload.get("location"),
            notes=payload.get("notes"),
        )
        return self._action_result(ACTION_ADD_CLASS_SESSION, result)

    def _handle_add_shift(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_academic_service()
        result = service.add_work_shift(
            title=payload["title"],
            start_at=payload["start_at"],
            end_at=payload["end_at"],
            location=payload.get("location"),
            role=payload.get("role"),
            energy_cost=payload.get("energy_cost"),
            notes=payload.get("notes"),
        )
        return self._action_result(ACTION_ADD_WORK_SHIFT, result)

    def _handle_add_note(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_knowledge_service()
        result = service.create_note(
            title=payload["title"],
            body=payload["body"],
            module_id=payload.get("module_id"),
            assignment_id=payload.get("assignment_id"),
            source_type="manual",
            tags=payload.get("tags"),
        )
        return self._action_result(ACTION_ADD_NOTE, result)

    def _handle_archive_note(self, payload: dict[str, Any]) -> ActionResult:
        service = self._build_knowledge_service()
        result = service.archive_note(payload["note_id"])
        return self._action_result(ACTION_ARCHIVE_NOTE, result)

    def _action_result(self, action_type: str, result: CommandResult) -> ActionResult:
        payload = {"record_id": result.record_id} if result.record_id else {}
        return ActionResult(
            action_type=action_type,
            outcome=ActionOutcome.SUCCESS if result.success else ActionOutcome.ERROR,
            message=result.message,
            payload=payload,
        )

    def _fallback(self, match: IntentMatch) -> str:
        query = match.slots.get("query", "")
        if query:
            return self._ask_notes({"query": query})
        return "I didn't understand that. Try asking about your schedule, assignments, or notes."

    def _confirm_add_assignment(self, slots: dict[str, str]) -> str:
        title = slots.get("title", "Untitled assignment")
        due = slots.get("due_at", "not specified")
        priority = slots.get("priority", "normal (inferred)")
        module = slots.get("module_name", slots.get("module_id", "not specified"))
        hours = slots.get("estimated_hours", "not specified")
        return (
            f"Add assignment?\n"
            f"Title: {title}\n"
            f"Due: {due}\n"
            f"Priority: {priority}\n"
            f"Module: {module}\n"
            f"Estimated hours: {hours}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_set_status(self, slots: dict[str, str]) -> str:
        assignment = slots.get(
            "assignment_title",
            slots.get("assignment_id", slots.get("assignment_id_or_title", "not specified")),
        )
        status = slots.get("status", "not specified")
        return (
            f"Update assignment status?\n"
            f"Assignment: {assignment}\n"
            f"Status: {status}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_set_hours(self, slots: dict[str, str]) -> str:
        assignment = slots.get("assignment_title", slots.get("assignment_id", "not specified"))
        completed = slots.get("completed_hours", "not specified")
        return (
            f"Update assignment hours?\n"
            f"Assignment: {assignment}\n"
            f"Completed: {completed}h\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_add_class(self, slots: dict[str, str]) -> str:
        title = slots.get("title", "Untitled class")
        module = slots.get("module_name", slots.get("module_id", "not specified"))
        return (
            f"Add class session?\n"
            f"Title: {title}\n"
            f"Weekday: {slots.get('weekday', 'not specified')}\n"
            f"Time: {slots.get('start_time', 'not specified')}-{slots.get('end_time', 'not specified')}\n"
            f"Module: {module}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_add_shift(self, slots: dict[str, str]) -> str:
        return (
            f"Add work shift?\n"
            f"Title: {slots.get('title', 'Work')}\n"
            f"Start: {slots.get('start_at', 'not specified')}\n"
            f"End: {slots.get('end_at', 'not specified')}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_add_note(self, slots: dict[str, str]) -> str:
        title = slots.get("title", "Untitled note")
        content_preview = slots.get("body", slots.get("content", ""))[:100]
        module = slots.get("module_name")
        assignment = slots.get("assignment_title")
        links = []
        if module:
            links.append(f"Module: {module}")
        if assignment:
            links.append(f"Assignment: {assignment}")
        link_block = ("\n" + "\n".join(links)) if links else ""
        return (
            f"Add note?\n"
            f"Title: {title}\n"
            f"Content: {content_preview}{link_block}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_archive_note(self, slots: dict[str, str]) -> str:
        return (
            f"Archive note?\n"
            f"Note: #{slots.get('note_id')} - {slots.get('note_title', 'Untitled note')}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

def _format_today(overview: object) -> str:
    classes = overview.classes
    work_shifts = overview.work_shifts
    deadlines = overview.deadlines
    availability = overview.availability
    if not classes and not work_shifts and not deadlines:
        return "\n".join([
            "Today",
            "",
            "No classes, work shifts, or deadlines found.",
            f"Available study time: {_format_duration(availability.total_study_minutes)}",
        ])
    lines = [f"Today - {_format_date(overview.date)}", ""]
    lines.extend(_format_block_section("Classes", classes, "No classes today"))
    lines.append("")
    lines.extend(_format_block_section("Work", work_shifts, "No work shifts today"))
    lines.append("")
    lines.extend(_format_window_section("Study windows", availability.study_windows))
    lines.append("")
    lines.extend(_format_deadline_section(deadlines))
    lines.append("")
    lines.append(f"Total study time: {_format_duration(availability.total_study_minutes)}")
    return "\n".join(lines)


def _format_week(overview: object) -> str:
    lines = [
        f"Week - {_format_short_date(overview.start_date)} to {_format_short_date(overview.end_date)}",
        "",
        "Summary",
        f"- Classes: {overview.class_count}",
        f"- Work shifts: {overview.work_shift_count}",
        f"- Open deadlines: {overview.open_deadline_count}",
        f"- Study time: {_format_duration(overview.availability.total_study_minutes)}",
        "",
    ]
    for summary in overview.day_summaries:
        lines.append(
            "{day}: classes {classes}, work {work}, study {study}".format(
                day=summary.date.strftime("%a"),
                classes=_format_duration(summary.class_minutes),
                work=_format_duration(summary.work_minutes),
                study=_format_duration(summary.study_minutes),
            )
        )
    return "\n".join(lines)


def _format_deadlines(assignments: list) -> str:
    if not assignments:
        return "No open deadlines found."
    lines = ["Upcoming deadlines"]
    for a in assignments:
        lines.append("")
        lines.append(f"- {_format_date(a.due_at.date())} - {a.title}")
        detail = f"  Priority: {a.priority} | Status: {a.status.value}"
        if a.estimated_hours is not None:
            detail += f" | Estimate: {_format_hours(a.estimated_hours)}"
        lines.append(detail)
    return "\n".join(lines)


def _format_availability(day: object) -> str:
    lines = ["Availability today", ""]
    if day.study_windows:
        for window in day.study_windows:
            lines.append(
                f"- {_format_time(window.start_at)}-{_format_time(window.end_at)} - {_format_duration(window.minutes)}"
            )
    else:
        lines.append("No study windows available today.")
    lines.append("")
    lines.append(f"Total: {_format_duration(day.total_study_minutes)}")
    return "\n".join(lines)


def _format_plan(plan: object) -> str:
    summary = plan.summary
    if (
        not plan.blocks
        and summary.total_required_minutes == 0
        and not summary.unestimated_assignments
        and not summary.overdue_assignments
    ):
        return "No open assignments to plan."
    if not plan.blocks and summary.total_required_minutes > 0 and summary.total_available_minutes == 0:
        lines = [
            "No study windows available this week.",
            "",
            f"Required workload: {_format_duration(summary.total_required_minutes)}",
            f"Unscheduled: {_format_duration(summary.total_unscheduled_minutes)}",
        ]
        return "\n".join(lines)
    lines = [
        f"Study plan - {_format_short_date(plan.start_date)} to {_format_short_date(plan.end_date)}",
        "",
        "Summary",
        f"- Available: {_format_duration(summary.total_available_minutes)}",
        f"- Required: {_format_duration(summary.total_required_minutes)}",
        f"- Planned: {_format_duration(summary.total_planned_minutes)}",
        f"- Unscheduled: {_format_duration(summary.total_unscheduled_minutes)}",
    ]
    if plan.blocks:
        current_day = None
        for block in sorted(plan.blocks, key=lambda item: (item.start_at, item.assignment_id)):
            day_label = block.start_at.strftime("%a")
            if day_label != current_day:
                current_day = day_label
                lines.extend(["", day_label])
            lines.append(
                f"- {_format_time(block.start_at)}-{_format_time(block.end_at)} {_study_block_title(block)}"
            )
    else:
        lines.extend(["", "No planned study blocks."])
    return "\n".join(lines)


def _format_study_recommendation(*, today_block, next_block, plan) -> str:
    if today_block is not None:
        return "\n".join([
            "Study next",
            "",
            f"Today {_format_time(today_block.start_at)}-{_format_time(today_block.end_at)} - {_study_block_title(today_block)}",
            f"Reason: {today_block.reason}",
            f"Due: {_format_date(today_block.due_at.date())}",
            f"Priority: {today_block.priority}",
        ])
    if next_block is not None:
        return "\n".join([
            "No more study blocks today.",
            "",
            "Next:",
            f"{_format_date(next_block.start_at.date())} {_format_time(next_block.start_at)}-{_format_time(next_block.end_at)} - {_study_block_title(next_block)}",
            f"Reason: {next_block.reason}",
        ])
    lines = [
        "No study recommendation available.",
        "",
        "Possible reasons:",
        "- no open assignments",
        "- assignments have no estimated hours",
        "- no available study windows",
    ]
    if plan.summary.unestimated_assignments:
        lines.append(f"- {len(plan.summary.unestimated_assignments)} assignments need estimated hours")
    return "\n".join(lines)


def _format_assignments(assignments: list) -> str:
    if not assignments:
        return "No open assignments found."
    lines = ["Assignments", ""]
    for a in assignments:
        lines.append(f"#{a.id[:8]} {a.title}")
        lines.append(f"  Due: {a.due_at.strftime('%a %d %b %H:%M')}")
        lines.append(f"  Status: {a.status.value}")
        if a.estimated_hours is not None:
            lines.append(f"  Estimate: {_format_hours(a.estimated_hours)}")
        if a.completed_hours > 0:
            lines.append(f"  Completed: {_format_hours(a.completed_hours)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_modules(modules: list) -> str:
    if not modules:
        return "No modules found."
    lines = ["Modules", ""]
    for m in modules:
        code = f" ({m.code})" if m.code else ""
        lines.append(f"#{m.id[:8]} {m.name}{code}")
    return "\n".join(lines)


def _format_shifts(shifts: list) -> str:
    if not shifts:
        return "No work shifts found."
    lines = ["Work shifts", ""]
    current_date = None
    for s in shifts:
        date_label = s.start_at.strftime("%a %d %b")
        if date_label != current_date:
            current_date = date_label
            lines.append(date_label)
        lines.append(f"  {s.start_at.strftime('%H:%M')}\u2013{s.end_at.strftime('%H:%M')} {s.title}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_llm_result(result: object, note_title: str) -> str:
    if not result.success:
        if "unavailable" in (result.error or "").lower() or "connection" in (result.error or "").lower():
            return "\n".join(_format_local_llm_error_lines(result.error))
        return f"Error: {result.error}"
    model_label = f"\nModel: {result.model}" if result.model else ""
    return f"{note_title}{model_label}\n\n{result.output[:2000]}"


def _format_retrieval_answer(result: object) -> str:
    if not result.success:
        error = result.error or "Retrieval failed."
        if "unavailable" in error.lower() or "connection" in error.lower():
            lines = _format_local_llm_error_lines(error)
            if result.sources:
                lines.extend(["", "Sources found"])
                lines.extend(_format_retrieval_source_lines(result.sources))
            return "\n".join(lines)
        return f"Error: {error}"
    if not result.sources:
        return result.answer
    lines = [f'Answer for "{result.question}"', ""]
    if result.model:
        lines.extend([f"Model: {result.model}", ""])
    lines.append(_truncate_text(result.answer, 1800))
    lines.extend(["", "Sources"])
    lines.extend(_format_retrieval_source_lines(result.sources))
    return "\n".join(lines).rstrip()


def _format_local_llm_error_lines(error: str | None) -> list[str]:
    error_text = (error or "").strip()
    lower_error = error_text.lower()
    if "ollama model unavailable" in lower_error or "ollama pull" in lower_error:
        return ["Local LLM model unavailable.", "", error_text]
    return ["Local LLM unavailable.", "", "Check that Ollama is running:", "ollama serve"]


def _format_retrieval_source_lines(sources) -> list[str]:
    lines = []
    for source in sources:
        lines.append(f"- [{source.chunk_label}] {source.title}")
        if source.snippet:
            lines.append(f"  {_truncate_text(source.snippet, 260)}")
    return lines


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _format_block_section(title: str, blocks: list, empty: str) -> list[str]:
    lines = [title]
    if not blocks:
        lines.append(f"- {empty}")
        return lines
    for block in blocks:
        lines.append(f"- {_format_time(block.start_at)}-{_format_time(block.end_at)} {block.title}")
    return lines


def _format_window_section(title: str, windows: list) -> list[str]:
    lines = [title]
    if not windows:
        lines.append("- No study windows available today")
        return lines
    for window in windows:
        lines.append(
            f"- {_format_time(window.start_at)}-{_format_time(window.end_at)} - {_format_duration(window.minutes)}"
        )
    return lines


def _format_deadline_section(assignments: list) -> list[str]:
    lines = ["Deadlines"]
    if not assignments:
        lines.append("- No open deadlines due soon")
        return lines
    for a in assignments:
        lines.append(f"- {a.title} - due {_format_date(a.due_at.date())}")
    return lines


def _format_time(value) -> str:
    return value.strftime("%H:%M")


def _format_date(value) -> str:
    return f"{value.strftime('%a')} {value.day} {value.strftime('%b')}"


def _format_short_date(value) -> str:
    return f"{value.day} {value.strftime('%b')}"


def _study_block_title(block) -> str:
    if block.module_name:
        return f"{block.assignment_title} ({block.module_name})"
    return block.assignment_title


def _format_duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h{remainder:02d}"


def _format_hours(hours: float) -> str:
    if hours.is_integer():
        return f"{int(hours)}h"
    return f"{hours:g}h"
