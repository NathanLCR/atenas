"""Telegram response formatters."""

from __future__ import annotations

from collections.abc import Sequence

from core.academic.models import Assignment, TimeBlock


def format_today(overview: object) -> str:
    classes = overview.classes
    work_shifts = overview.work_shifts
    deadlines = overview.deadlines
    availability = overview.availability
    if not classes and not work_shifts and not deadlines:
        return "\n".join([
            "Today", "",
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


def format_week(overview: object) -> str:
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


def format_deadlines(assignments: list[Assignment]) -> str:
    if not assignments:
        return "No open deadlines found."
    lines = ["Upcoming deadlines"]
    for assignment in assignments:
        lines.append("")
        lines.append(f"- {_format_date(assignment.due_at.date())} - {assignment.title}")
        detail = f"  Priority: {assignment.priority} | Status: {assignment.status.value}"
        if assignment.estimated_hours is not None:
            detail += f" | Estimate: {_format_hours(assignment.estimated_hours)}"
        lines.append(detail)
    return "\n".join(lines)


def format_availability(day: object) -> str:
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


def format_plan(plan: object) -> str:
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
        lines.extend(_format_plan_warnings(plan))
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
    lines.extend(_format_plan_warnings(plan))
    return "\n".join(lines)


def format_study_recommendation(
    *,
    today_block: object | None,
    next_block: object | None,
    plan: object,
) -> str:
    if today_block is not None:
        return "\n".join([
            "Study next", "",
            f"Today {_format_time(today_block.start_at)}-{_format_time(today_block.end_at)} - {_study_block_title(today_block)}",
            f"Reason: {today_block.reason}",
            f"Due: {_format_date(today_block.due_at.date())}",
            f"Priority: {today_block.priority}",
        ])

    if next_block is not None:
        return "\n".join([
            "No more study blocks today.", "",
            "Next:",
            f"{_format_date(next_block.start_at.date())} {_format_time(next_block.start_at)}-{_format_time(next_block.end_at)} - {_study_block_title(next_block)}",
            f"Reason: {next_block.reason}",
        ])

    lines = [
        "No study recommendation available.", "",
        "Possible reasons:",
        "- no open assignments",
        "- assignments have no estimated hours",
        "- no available study windows",
    ]
    if plan.summary.unestimated_assignments:
        lines.append(f"- {len(plan.summary.unestimated_assignments)} assignments need estimated hours")
    return "\n".join(lines)


def format_retrieval_answer(result: object) -> str:
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


def format_llm_result(result: object, note_title: str) -> str:
    if not result.success:
        if "unavailable" in (result.error or "").lower() or "connection" in (result.error or "").lower():
            return "\n".join(_format_local_llm_error_lines(result.error))
        return f"Error: {result.error}"

    model_label = f"\nModel: {result.model}" if result.model else ""
    return f"{note_title}{model_label}\n\n{result.output[:2000]}"


def _format_block_section(title: str, blocks: list[TimeBlock], empty: str) -> list[str]:
    lines = [title]
    if not blocks:
        lines.append(f"- {empty}")
        return lines
    for block in blocks:
        lines.append(f"- {_format_time(block.start_at)}-{_format_time(block.end_at)} {block.title}")
    return lines


def _format_window_section(title: str, windows: list[object]) -> list[str]:
    lines = [title]
    if not windows:
        lines.append("- No study windows available today")
        return lines
    for window in windows:
        lines.append(
            f"- {_format_time(window.start_at)}-{_format_time(window.end_at)} - {_format_duration(window.minutes)}"
        )
    return lines


def _format_deadline_section(assignments: list[Assignment]) -> list[str]:
    lines = ["Deadlines"]
    if not assignments:
        lines.append("- No open deadlines due soon")
        return lines
    for assignment in assignments:
        lines.append(f"- {assignment.title} - due {_format_date(assignment.due_at.date())}")
    return lines


def _format_plan_warnings(plan: object) -> list[str]:
    summary = plan.summary
    warnings: list[str] = []
    if summary.total_required_minutes > summary.total_available_minutes:
        warnings.append("- Required workload exceeds available study time")
    for item in plan.unscheduled:
        warnings.append(
            "- {title}: {minutes} unscheduled before deadline".format(
                title=item.assignment_title,
                minutes=_format_duration(item.unscheduled_minutes),
            )
        )
    if summary.unestimated_assignments:
        warnings.append(f"- {len(summary.unestimated_assignments)} assignments need estimated hours")
    if summary.overdue_assignments:
        warnings.append(f"- {len(summary.overdue_assignments)} overdue assignments")
    if not warnings:
        return []
    return ["", "Warnings", *warnings]


def _format_local_llm_error_lines(error: str | None) -> list[str]:
    error_text = (error or "").strip()
    lower_error = error_text.lower()
    if "ollama model unavailable" in lower_error or "ollama pull" in lower_error:
        return ["Local LLM model unavailable.", "", error_text]
    return ["Local LLM unavailable.", "", "Check that Ollama is running:", "ollama serve"]


def _format_retrieval_source_lines(sources: Sequence[object]) -> list[str]:
    lines: list[str] = []
    for source in sources:
        lines.append(f"- [{source.chunk_label}] {source.title}")
        if source.snippet:
            lines.append(f"  {_truncate_text(source.snippet, 260)}")
    return lines


def _study_block_title(block: object) -> str:
    if block.module_name:
        return f"{block.assignment_title} ({block.module_name})"
    return block.assignment_title


def _format_time(value: object) -> str:
    return value.strftime("%H:%M")


def _format_date(value: object) -> str:
    return f"{value.strftime('%a')} {value.day} {value.strftime('%b')}"


def _format_short_date(value: object) -> str:
    return f"{value.day} {value.strftime('%b')}"


def _format_duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h{remainder:02d}"


def _format_hours(hours: float) -> str:
    if hours.is_integer():
        return f"{int(hours)}h"
    return f"{hours:g}h"


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."
