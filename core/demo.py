"""Synthetic demo data so a new user can evaluate Atenas without Telegram.

All names are fictional. Dates are computed relative to "today" in the
supplied timezone, and everything is written through the regular services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.service import AcademicService
from core.db import init_db
from core.knowledge.service import KnowledgeService
from core.schemas import FatigueLevel


class DemoSeedError(RuntimeError):
    """Raised when demo data cannot be seeded safely."""


@dataclass(frozen=True)
class DemoSummary:
    """Counts of what was seeded."""

    modules: int
    classes: int
    shifts: int
    assignments: int
    notes: int


# (code, name, lecturer)
_MODULES = [
    ("QNT101", "Quantum Gardening", "Dr. Ada Fernsby"),
    ("LIT220", "Applied Dragonology", "Prof. Orin Maple"),
    ("MTH310", "Cartography of Imaginary Spaces", "Dr. Lumi Okafor"),
    ("ENG150", "Workshop Robotics for Teapots", "Ms. Pia Thornwood"),
]

# (module index, weekday Mon=0, start, end, location)
_CLASSES = [
    (0, 0, "09:00", "11:00", "Lab 1"),
    (1, 0, "14:00", "16:00", "Room 2.04"),
    (2, 1, "10:00", "12:00", "Room 1.11"),
    (3, 2, "13:00", "15:00", "Workshop B"),
    (0, 3, "09:00", "10:30", "Lab 1"),
    (1, 4, "11:00", "13:00", "Room 2.04"),
]

# (title, day offset from today, start, end, fatigue, role)
_SHIFTS = [
    ("Cafe evening close", 1, time(17, 0), time(23, 30), FatigueLevel.HIGH, "Closing"),
    ("Cafe lunch cover", 2, time(11, 30), time(15, 0), FatigueLevel.LOW, "Counter"),
    ("Cafe weekend rush", 4, time(10, 0), time(18, 0), FatigueLevel.MEDIUM, "Floor"),
    ("Cafe late bar", 5, time(16, 0), time(23, 0), FatigueLevel.HIGH, "Bar"),
]

# (module index, title, hours until due, priority, estimated hours, completed)
_ASSIGNMENTS = [
    (0, "Greenhouse Entanglement Report", 40, 1, 6, 1),
    (1, "Dragon Taxonomy Essay", 60, 2, 5, 0),
    (2, "Map of Nowhere Portfolio", 5 * 24, 2, 8, 0),
    (3, "Teapot Servo Prototype", 6 * 24, 3, 10, 2),
    (0, "Seed Superposition Problem Set", 9 * 24, 3, 4, 0),
    (1, "Dragon Habitat Quiz Prep", 12 * 24, 4, 3, 0),
]

_NOTES = [
    (
        "Quantum Gardening: lecture 3 summary",
        "Plants in superposition are watered only when observed.\n"
        "Key terms: observer effect, soil decoherence, compost entropy.",
        0,
        "lecture",
        ["demo", "lecture"],
    ),
    (
        "Dragon Taxonomy reading list",
        "Start with the field guide chapters 1-4, then the habitat survey.\n"
        "Compare scale types across the northern and southern ranges.",
        1,
        "reading",
        ["demo", "reading"],
    ),
    (
        "Teapot servo wiring checklist",
        "Check lid sensor polarity, then calibrate the pour angle servo.\n"
        "Keep wiring diagrams in the prototype folder.",
        3,
        "manual",
        ["demo", "project"],
    ),
]


def seed_demo_data(
    db_path: Path | str,
    timezone: str | ZoneInfo = "UTC",
    now: datetime | None = None,
    *,
    force: bool = False,
    allowed_file_roots: list[Path | str] | None = None,
) -> DemoSummary:
    """Seed a synthetic study week; refuse if modules exist unless ``force``."""

    tz = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
    now_local = datetime.now(tz) if now is None else now.astimezone(tz)
    init_db(db_path)
    academic = AcademicService(db_path, timezone=tz)
    if academic.list_modules() and not force:
        raise DemoSeedError(
            "Database already contains modules; refusing to add demo data "
            "(use --force to seed anyway)."
        )

    modules = [
        academic.create_module(name=name, code=code, lecturer=lecturer)
        for code, name, lecturer in _MODULES
    ]
    for index, weekday, start, end, location in _CLASSES:
        module = modules[index]
        academic.create_class_session(
            title=f"{module.name} lecture",
            weekday=weekday,
            start_time=start,
            end_time=end,
            module_id=module.id,
            location=location,
        )

    today = now_local.date()
    for title, offset, start, end, fatigue, role in _SHIFTS:
        day = today + timedelta(days=offset)
        academic.create_work_shift(
            title=title,
            start_at=datetime.combine(day, start, tzinfo=tz),
            end_at=datetime.combine(day, end, tzinfo=tz),
            role=role,
            fatigue_level=fatigue,
        )

    for index, title, hours, priority, estimate, done in _ASSIGNMENTS:
        academic.create_assignment(
            title=title,
            due_at=now_local + timedelta(hours=hours),
            module_id=modules[index].id,
            priority=priority,
            estimated_hours=estimate,
            completed_hours=done,
        )

    knowledge = KnowledgeService(db_path, timezone=tz, allowed_file_roots=allowed_file_roots)
    notes_created = 0
    for title, body, index, source_type, tags in _NOTES:
        result = knowledge.create_note(
            title, body, module_id=modules[index].id, source_type=source_type, tags=tags
        )
        notes_created += 1 if result.success else 0

    return DemoSummary(
        modules=len(modules),
        classes=len(_CLASSES),
        shifts=len(_SHIFTS),
        assignments=len(_ASSIGNMENTS),
        notes=notes_created,
    )
