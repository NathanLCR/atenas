"""Natural language router: maps IntentMatch to existing service/command calls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from core.academic.service import AcademicService
from core.academic.validators import CommandResult, parse_kv_args
from core.knowledge.service import KnowledgeService
from core.llm.service import LLMService
from core.nl.intent import (
    INTENT_ADD_ASSIGNMENT,
    INTENT_ADD_NOTE,
    INTENT_ASK_NOTES,
    INTENT_AVAILABILITY,
    INTENT_DEADLINES,
    INTENT_LIST_ASSIGNMENTS,
    INTENT_LIST_MODULES,
    INTENT_LIST_SHIFTS,
    INTENT_NOTE_ACTION,
    INTENT_PLAN,
    INTENT_REMINDERS,
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

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

SLASH_COMMAND_SUGGESTIONS: dict[str, str] = {
    INTENT_TODAY: "/today",
    INTENT_WEEK: "/week",
    INTENT_DEADLINES: "/deadlines",
    INTENT_AVAILABILITY: "/availability",
    INTENT_PLAN: "/plan",
    INTENT_STUDY: "/study",
    INTENT_ADD_ASSIGNMENT: "/add_assignment",
    INTENT_SET_STATUS: "/set_status",
    INTENT_LIST_ASSIGNMENTS: "/assignments",
    INTENT_LIST_MODULES: "/modules",
    INTENT_LIST_SHIFTS: "/shifts",
    INTENT_ADD_NOTE: "/add_note",
    INTENT_NOTE_ACTION: "/summarize_note or /explain_note",
    INTENT_ASK_NOTES: "/ask_notes",
    INTENT_REMINDERS: "/reminders",
}


class NLRouter:
    """Routes classified intents to existing service calls."""

    def __init__(
        self,
        db_path: Path,
        timezone: str = "Europe/Dublin",
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1:8b",
        ollama_timeout: int = 60,
    ) -> None:
        self._db_path = db_path
        self._tz = timezone
        self._ollama_base_url = ollama_base_url
        self._ollama_model = ollama_model
        self._ollama_timeout = ollama_timeout

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

    def build_confirmation(self, match: IntentMatch) -> str:
        """Build a confirmation message for a write intent."""
        if match.intent == INTENT_ADD_ASSIGNMENT:
            return self._confirm_add_assignment(match.slots)
        if match.intent == INTENT_SET_STATUS:
            return self._confirm_set_status(match.slots)
        if match.intent == INTENT_ADD_NOTE:
            return self._confirm_add_note(match.slots)
        return "I'm not sure what to do. Try /help."

    def execute_write(self, match: IntentMatch) -> str:
        """Execute a confirmed write intent and return the result."""
        if match.intent == INTENT_ADD_ASSIGNMENT:
            return self._execute_add_assignment(match.slots)
        if match.intent == INTENT_SET_STATUS:
            return self._execute_set_status(match.slots)
        if match.intent == INTENT_ADD_NOTE:
            return self._execute_add_note(match.slots)
        return "Unknown write intent."

    def suggest_command(self, match: IntentMatch) -> str:
        """Suggest the closest slash command for an unclear intent."""
        cmd = SLASH_COMMAND_SUGGESTIONS.get(match.intent)
        if cmd:
            return f"I'm not entirely sure what you mean. Try: {cmd}"
        return f"I didn't understand that. You can try /ask_notes with your question, or use /status to see available commands."

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

    def _fallback(self, match: IntentMatch) -> str:
        query = match.slots.get("query", "")
        if query:
            return self._ask_notes({"query": query})
        return "I didn't understand that. Try asking about your schedule, assignments, or notes."

    def _confirm_add_assignment(self, slots: dict[str, str]) -> str:
        title = slots.get("title", "Untitled assignment")
        due = slots.get("due_at", "not specified")
        priority = slots.get("priority", "normal (inferred)")
        module = slots.get("module", "not specified")
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
        assignment = slots.get("assignment_id_or_title", slots.get("assignment", "not specified"))
        status = slots.get("status", "not specified")
        return (
            f"Update assignment status?\n"
            f"Assignment: {assignment}\n"
            f"Status: {status}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _confirm_add_note(self, slots: dict[str, str]) -> str:
        title = slots.get("title", "Untitled note")
        content_preview = slots.get("content", "")[:100]
        return (
            f"Add note?\n"
            f"Title: {title}\n"
            f"Content: {content_preview}\n"
            f'Reply "yes" to confirm or "no" to cancel.'
        )

    def _execute_add_assignment(self, slots: dict[str, str]) -> str:
        service = self._build_academic_service()
        title = slots.get("title")
        due = slots.get("due_at")
        if not title or not due:
            return "Missing title or due date. Use: /add_assignment title=\"...\" due=\"...\""
        priority_str = slots.get("priority", "3")
        priority = int(priority_str) if priority_str.isdigit() else 3
        estimate_str = slots.get("estimated_hours")
        estimated = float(estimate_str) if estimate_str and estimate_str.replace(".", "").isdigit() else None
        module_id = slots.get("module")
        result = service.add_assignment(
            title=title,
            due_at=due,
            module_id=module_id or None,
            priority=priority,
            estimated_hours=estimated,
        )
        return result.message

    def _execute_set_status(self, slots: dict[str, str]) -> str:
        service = self._build_academic_service()
        assignment_id = slots.get("assignment_id_or_title", slots.get("assignment"))
        status = slots.get("status")
        if not assignment_id or not status:
            return "Missing assignment or status. Use: /set_status assignment=... status=..."
        result = service.update_assignment_status(assignment_id, status)
        return result.message

    def _execute_add_note(self, slots: dict[str, str]) -> str:
        service = self._build_knowledge_service()
        title = slots.get("title")
        body = slots.get("content", slots.get("body", ""))
        if not title:
            return "Missing note title. Use: /add_note title=\"...\" body=\"...\""
        result = service.create_note(title=title, body=body, source_type="manual")
        return result.message


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
            return "Local LLM unavailable.\n\nCheck that Ollama is running:\nollama serve"
        return f"Error: {result.error}"
    model_label = f"\nModel: {result.model}" if result.model else ""
    return f"{note_title}{model_label}\n\n{result.output[:2000]}"


def _format_retrieval_answer(result: object) -> str:
    if not result.success:
        error = result.error or "Retrieval failed."
        if "unavailable" in error.lower() or "connection" in error.lower():
            lines = ["Local LLM unavailable.", "", "Check that Ollama is running:", "ollama serve"]
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
