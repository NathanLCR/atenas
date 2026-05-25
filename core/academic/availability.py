"""Deterministic availability calculation for classes and work shifts."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.academic.models import (
    ClassSession,
    DayAvailability,
    StudyWindow,
    TimeBlock,
    WeekAvailability,
    WorkShift,
)
from core.schemas import FatigueLevel
from core.time import combine_local, ensure_local_datetime, iter_dates, parse_hhmm

DEFAULT_DAY_START = time(8, 0)
DEFAULT_DAY_END = time(22, 0)
DEFAULT_MINIMUM_STUDY_WINDOW_MINUTES = 45
HEAVY_WEEK_SHIFT_THRESHOLD = 4
HEAVY_WEEK_CAPACITY_MULTIPLIER = 0.7


def calculate_availability(
    start_date: date,
    end_date: date,
    class_sessions: list[ClassSession],
    work_shifts: list[WorkShift],
    timezone: ZoneInfo,
    now: datetime | None = None,
    day_start: time = DEFAULT_DAY_START,
    day_end: time = DEFAULT_DAY_END,
    minimum_study_window_minutes: int = DEFAULT_MINIMUM_STUDY_WINDOW_MINUTES,
) -> WeekAvailability:
    """Return study availability for an inclusive local date range."""

    now_local = ensure_local_datetime(now, timezone) if now is not None else None
    heavy_shift_week = len(work_shifts) >= HEAVY_WEEK_SHIFT_THRESHOLD
    days = [
        _calculate_day(
            day=day,
            class_sessions=class_sessions,
            work_shifts=work_shifts,
            timezone=timezone,
            now=now_local,
            day_start=day_start,
            day_end=day_end,
            minimum_study_window_minutes=minimum_study_window_minutes,
            heavy_shift_week=heavy_shift_week,
        )
        for day in iter_dates(start_date, end_date)
    ]
    return WeekAvailability(
        start_date=start_date,
        end_date=end_date,
        days=days,
        total_study_minutes=sum(day.total_study_minutes for day in days),
    )


def _calculate_day(
    day: date,
    class_sessions: list[ClassSession],
    work_shifts: list[WorkShift],
    timezone: ZoneInfo,
    now: datetime | None,
    day_start: time,
    day_end: time,
    minimum_study_window_minutes: int,
    heavy_shift_week: bool,
) -> DayAvailability:
    boundary_start = combine_local(day, day_start, timezone)
    boundary_end = combine_local(day, day_end, timezone)
    raw_blocks = _class_blocks(day, class_sessions, timezone)
    raw_blocks.extend(_work_blocks(work_shifts))
    clipped_blocks = [
        clipped
        for block in raw_blocks
        if (clipped := _clip_block(block, boundary_start, boundary_end)) is not None
    ]
    blocked = _merge_blocks(clipped_blocks)
    study_windows = _free_windows(
        blocked,
        boundary_start,
        boundary_end,
        now if now is not None and now.date() == day else None,
        minimum_study_window_minutes,
        work_shifts=work_shifts,
    )
    if heavy_shift_week:
        study_windows = _apply_heavy_week_reserve(
            study_windows,
            minimum_study_window_minutes,
        )
    return DayAvailability(
        date=day,
        blocked=blocked,
        study_windows=study_windows,
        total_study_minutes=sum(window.minutes for window in study_windows),
    )


def _max_intensity_for_window(start_at: datetime, work_shifts: list[WorkShift]) -> str:
    """Return max intensity cap for a study window based on prior work fatigue."""
    previous_late_high = any(
        getattr(shift, "fatigue_level", None) == FatigueLevel.HIGH
        and shift.end_at.date() == start_at.date() - timedelta(days=1)
        and shift.end_at.hour >= 23
        for shift in work_shifts
    )
    if previous_late_high and start_at.hour < 10:
        return "light"
    same_day_high = any(
        getattr(shift, "fatigue_level", None) == FatigueLevel.HIGH
        and shift.start_at.date() == start_at.date()
        for shift in work_shifts
    )
    if same_day_high:
        return "light"
    return "deep"


def _class_blocks(
    day: date,
    class_sessions: list[ClassSession],
    timezone: ZoneInfo,
) -> list[TimeBlock]:
    blocks: list[TimeBlock] = []
    for session in class_sessions:
        if not session.active or session.weekday != day.weekday():
            continue
        start_at = combine_local(day, parse_hhmm(session.start_time), timezone)
        end_at = combine_local(day, parse_hhmm(session.end_time), timezone)
        blocks.append(
            TimeBlock(
                title=session.title,
                start_at=start_at,
                end_at=end_at,
                kind="class",
                metadata={"session_id": session.id, "module_id": session.module_id},
            )
        )
    return blocks


def _work_blocks(work_shifts: list[WorkShift]) -> list[TimeBlock]:
    return [
        TimeBlock(
            title=shift.title,
            start_at=shift.start_at,
            end_at=shift.end_at,
            kind="work",
            metadata={"shift_id": shift.id, "role": shift.role},
        )
        for shift in work_shifts
    ]


def _clip_block(
    block: TimeBlock,
    boundary_start: datetime,
    boundary_end: datetime,
) -> TimeBlock | None:
    if block.end_at <= boundary_start or block.start_at >= boundary_end:
        return None
    return TimeBlock(
        title=block.title,
        start_at=max(block.start_at, boundary_start),
        end_at=min(block.end_at, boundary_end),
        kind=block.kind,
        metadata=block.metadata,
    )


def _merge_blocks(blocks: list[TimeBlock]) -> list[TimeBlock]:
    if not blocks:
        return []
    ordered = sorted(blocks, key=lambda block: (block.start_at, block.end_at))
    merged = [ordered[0]]
    for block in ordered[1:]:
        current = merged[-1]
        if block.start_at <= current.end_at:
            merged[-1] = _merge_pair(current, block)
        else:
            merged.append(block)
    return merged


def _merge_pair(first: TimeBlock, second: TimeBlock) -> TimeBlock:
    titles = _metadata_list(first, "titles", first.title)
    titles.extend(_metadata_list(second, "titles", second.title))
    kinds = _metadata_list(first, "kinds", first.kind)
    kinds.extend(_metadata_list(second, "kinds", second.kind))
    unique_titles = list(dict.fromkeys(str(title) for title in titles))
    unique_kinds = list(dict.fromkeys(str(kind) for kind in kinds))
    kind = first.kind if len(unique_kinds) == 1 else "manual"
    return TimeBlock(
        title="; ".join(unique_titles),
        start_at=min(first.start_at, second.start_at),
        end_at=max(first.end_at, second.end_at),
        kind=kind,
        metadata={"titles": unique_titles, "kinds": unique_kinds},
    )


def _metadata_list(block: TimeBlock, key: str, fallback: object) -> list[object]:
    value = block.metadata.get(key)
    if isinstance(value, list):
        return list(value)
    return [fallback]


def _free_windows(
    blocked: list[TimeBlock],
    boundary_start: datetime,
    boundary_end: datetime,
    now: datetime | None,
    minimum_study_window_minutes: int,
    work_shifts: list[WorkShift] | None = None,
) -> list[StudyWindow]:
    cursor = max(boundary_start, now) if now is not None else boundary_start
    if cursor >= boundary_end:
        return []

    windows: list[StudyWindow] = []
    for block in blocked:
        if block.end_at <= cursor:
            continue
        if block.start_at > cursor:
            _append_window(windows, cursor, block.start_at, minimum_study_window_minutes, work_shifts=work_shifts)
        cursor = max(cursor, block.end_at)
        if cursor >= boundary_end:
            return windows
    _append_window(windows, cursor, boundary_end, minimum_study_window_minutes, work_shifts=work_shifts)
    return windows


def _append_window(
    windows: list[StudyWindow],
    start_at: datetime,
    end_at: datetime,
    minimum_study_window_minutes: int,
    work_shifts: list[WorkShift] | None = None,
) -> None:
    minutes = int((end_at - start_at).total_seconds() // 60)
    if minutes >= minimum_study_window_minutes:
        windows.append(StudyWindow(
            start_at=start_at,
            end_at=end_at,
            minutes=minutes,
            max_intensity=_max_intensity_for_window(start_at, work_shifts or []),
        ))


def _apply_heavy_week_reserve(
    windows: list[StudyWindow],
    minimum_study_window_minutes: int,
) -> list[StudyWindow]:
    """Keep a deterministic recovery reserve when the week has four or more shifts."""
    total_minutes = sum(window.minutes for window in windows)
    target_minutes = int(total_minutes * HEAVY_WEEK_CAPACITY_MULTIPLIER)
    remaining = target_minutes
    reserved: list[StudyWindow] = []
    for window in windows:
        if remaining < minimum_study_window_minutes:
            break
        minutes = min(window.minutes, remaining)
        if minutes < minimum_study_window_minutes:
            break
        reserved.append(
            window.model_copy(
                update={
                    "end_at": window.start_at + timedelta(minutes=minutes),
                    "minutes": minutes,
                }
            )
        )
        remaining -= minutes
    return reserved
