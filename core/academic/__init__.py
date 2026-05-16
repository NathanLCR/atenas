"""Academic scheduling foundation for Atenas."""

from core.academic.models import (
    Assignment,
    AssignmentStatus,
    ClassSession,
    DayAvailability,
    StudyModule,
    StudyWindow,
    TimeBlock,
    WeekAvailability,
    WorkShift,
)
from core.academic.repository import AcademicRepository
from core.academic.service import AcademicService

__all__ = [
    "AcademicRepository",
    "AcademicService",
    "Assignment",
    "AssignmentStatus",
    "ClassSession",
    "DayAvailability",
    "StudyModule",
    "StudyWindow",
    "TimeBlock",
    "WeekAvailability",
    "WorkShift",
]
