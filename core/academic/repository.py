"""SQLite repository for academic scheduling data."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.models import (
    Assignment,
    AssignmentStatus,
    ClassSession,
    StudyModule,
    WorkShift,
)
from core.db import get_connection
from core.time import ensure_local_datetime, parse_due_at, parse_hhmm

COMPLETED_STATUSES = {
    AssignmentStatus.SUBMITTED.value,
    AssignmentStatus.DONE.value,
    AssignmentStatus.CANCELLED.value,
    "graded",
    "archived",
}


class AcademicRepository:
    """Persistence boundary for Phase 3 scheduling records."""

    def __init__(self, db_path: Path | str, timezone: ZoneInfo) -> None:
        self.db_path = db_path
        self.timezone = timezone

    def create_module(self, module: StudyModule) -> StudyModule:
        """Insert and return a study module."""

        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO study_modules (
                    id, code, name, lecturer, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    module.id,
                    module.code,
                    module.name,
                    module.lecturer,
                    module.notes,
                    module.created_at,
                    module.updated_at,
                ),
            )
            connection.commit()
        return module

    def list_modules(self) -> list[StudyModule]:
        """Return modules ordered by code and name."""

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM study_modules
                ORDER BY COALESCE(code, ''), name
                """
            ).fetchall()
        return [self._module_from_row(row) for row in rows]

    def create_class_session(self, session: ClassSession) -> ClassSession:
        """Insert and return a weekly class session."""

        values = (
            session.id,
            session.module_id,
            session.title,
            session.weekday,
            session.start_time,
            session.end_time,
            session.location,
            session.recurrence,
            1 if session.active else 0,
            session.notes,
            session.created_at,
            session.updated_at,
        )
        with get_connection(self.db_path) as connection:
            try:
                self._insert_class_session(connection, values)
            except sqlite3.IntegrityError as exc:
                if "class_sessions.module_id" not in str(exc) or session.module_id is not None:
                    raise
                legacy_values = (values[0], "", *values[2:])
                self._insert_class_session(connection, legacy_values)
            connection.commit()
        return session

    def list_class_sessions(self, active_only: bool = True) -> list[ClassSession]:
        """Return schedulable weekly class sessions."""

        if active_only:
            query = """
                SELECT *
                FROM class_sessions
                WHERE active = 1
                ORDER BY weekday, start_time, title
                """
        else:
            query = """
                SELECT *
                FROM class_sessions
                ORDER BY weekday, start_time, title
                """
        with get_connection(self.db_path) as connection:
            rows = connection.execute(query).fetchall()
        sessions: list[ClassSession] = []
        for row in rows:
            if row["weekday"] is None:
                continue
            sessions.append(self._class_session_from_row(row))
        return sessions

    def create_work_shift(self, shift: WorkShift) -> WorkShift:
        """Insert and return a date-specific work shift."""

        start_at = ensure_local_datetime(shift.start_at, self.timezone)
        end_at = ensure_local_datetime(shift.end_at, self.timezone)
        stored_shift = shift.model_copy(update={"start_at": start_at, "end_at": end_at})
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO work_shifts (
                    id, title, date, workplace, start_time, end_time, start_at,
                    end_at, location, role, energy_cost, commute_minutes,
                    fatigue_level, notes, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'medium', ?, 'phase3', ?, ?)
                """,
                (
                    stored_shift.id,
                    stored_shift.title,
                    start_at.date().isoformat(),
                    stored_shift.location,
                    start_at.strftime("%H:%M"),
                    end_at.strftime("%H:%M"),
                    start_at.isoformat(),
                    end_at.isoformat(),
                    stored_shift.location,
                    stored_shift.role,
                    stored_shift.energy_cost,
                    stored_shift.notes,
                    stored_shift.created_at,
                    stored_shift.updated_at,
                ),
            )
            connection.commit()
        return stored_shift

    def list_work_shifts(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[WorkShift]:
        """Return work shifts, optionally filtered by local date intersection."""

        conditions = []
        params: list[object] = []
        if start_date is not None:
            conditions.append("date <= ?")
            params.append(end_date.isoformat() if end_date else date.max.isoformat())
        if end_date is not None:
            conditions.append("date >= ?")
            params.append(start_date.isoformat() if start_date else date.min.isoformat())

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM work_shifts
                {where}
                ORDER BY date, start_time, title
                """,
                params,
            ).fetchall()
        return [self._work_shift_from_row(row) for row in rows]

    def create_assignment(self, assignment: Assignment) -> Assignment:
        """Insert and return an assignment/deadline."""

        due_at = ensure_local_datetime(assignment.due_at, self.timezone)
        stored_assignment = assignment.model_copy(update={"due_at": due_at})
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO assignments (
                    id, title, module_id, description, due_date, due_at, status,
                    priority, priority_rank, weight, estimated_hours, completed_hours, notes,
                    brief_path, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored_assignment.id,
                    stored_assignment.title,
                    stored_assignment.module_id,
                    None,
                    due_at.date().isoformat(),
                    due_at.isoformat(),
                    stored_assignment.status.value,
                    _priority_label(stored_assignment.priority),
                    stored_assignment.priority,
                    stored_assignment.weight,
                    stored_assignment.estimated_hours,
                    stored_assignment.completed_hours,
                    stored_assignment.notes,
                    None,
                    stored_assignment.created_at,
                    stored_assignment.updated_at,
                ),
            )
            connection.commit()
        return stored_assignment

    def list_upcoming_assignments(
        self,
        limit: int = 10,
        include_completed: bool = False,
    ) -> list[Assignment]:
        """Return deadlines sorted by due date, then priority."""

        status_filter = ""
        if not include_completed:
            placeholders = ", ".join("?" for _ in COMPLETED_STATUSES)
            status_filter = f" AND status NOT IN ({placeholders})"

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM assignments
                WHERE COALESCE(due_at, due_date) IS NOT NULL{status_filter}
                ORDER BY COALESCE(due_at, due_date), priority_rank, LOWER(title)
                LIMIT ?
                """,
                list(COMPLETED_STATUSES) + [limit] if not include_completed else [limit],
            ).fetchall()
        return [self._assignment_from_row(row) for row in rows]

    def list_all_assignments(self, include_completed: bool = True) -> list[Assignment]:
        """Return all assignments sorted by due date."""

        status_filter = ""
        params: list[object] = []
        if not include_completed:
            placeholders = ", ".join("?" for _ in COMPLETED_STATUSES)
            status_filter = f" AND status NOT IN ({placeholders})"
            params = list(COMPLETED_STATUSES)

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM assignments
                WHERE COALESCE(due_at, due_date) IS NOT NULL{status_filter}
                ORDER BY COALESCE(due_at, due_date), priority_rank, LOWER(title)
                """,
                params,
            ).fetchall()
        return [self._assignment_from_row(row) for row in rows]

    def list_all_work_shifts(self, limit: int = 50) -> list[WorkShift]:
        """Return upcoming work shifts."""

        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM work_shifts
                WHERE start_at IS NOT NULL
                ORDER BY start_at
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._work_shift_from_row(row) for row in rows]

    def update_assignment_status(self, assignment_id: str, status: AssignmentStatus) -> bool:
        """Update assignment status. Returns True if row was found and updated."""

        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE assignments
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, connection.execute("SELECT datetime('now')").fetchone()[0], assignment_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def update_completed_hours(self, assignment_id: str, completed_hours: float) -> bool:
        """Update assignment completed hours. Returns True if row was found."""

        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE assignments
                SET completed_hours = ?, updated_at = ?
                WHERE id = ?
                """,
                (completed_hours, connection.execute("SELECT datetime('now')").fetchone()[0], assignment_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def get_assignment_by_id(self, assignment_id: str) -> Assignment | None:
        """Return a single assignment by ID."""

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM assignments WHERE id = ?",
                (assignment_id,),
            ).fetchone()
        if row is None:
            return None
        return self._assignment_from_row(row)

    def get_module_by_id(self, module_id: str) -> StudyModule | None:
        """Return a single module by ID."""

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM study_modules WHERE id = ?",
                (module_id,),
            ).fetchone()
        if row is None:
            return None
        return self._module_from_row(row)

    def find_duplicate_module(self, name: str, code: str | None) -> StudyModule | None:
        """Find existing module with same normalized name and code."""

        with get_connection(self.db_path) as connection:
            if code:
                row = connection.execute(
                    """
                    SELECT * FROM study_modules
                    WHERE LOWER(name) = LOWER(?) AND LOWER(COALESCE(code, '')) = LOWER(?)
                    """,
                    (name, code),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM study_modules
                    WHERE LOWER(name) = LOWER(?) AND code IS NULL
                    """,
                    (name,),
                ).fetchone()
        if row is None:
            return None
        return self._module_from_row(row)

    def find_duplicate_class_session(
        self, title: str, weekday: int, start_time: str, end_time: str
    ) -> ClassSession | None:
        """Find existing class session with same title, weekday, and times."""

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM class_sessions
                WHERE LOWER(title) = LOWER(?) AND weekday = ?
                  AND start_time = ? AND end_time = ?
                """,
                (title, weekday, start_time, end_time),
            ).fetchone()
        if row is None:
            return None
        return self._class_session_from_row(row)

    def find_duplicate_work_shift(self, title: str, start_at: str, end_at: str) -> WorkShift | None:
        """Find existing work shift with same title, start_at, and end_at."""

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM work_shifts
                WHERE LOWER(COALESCE(title, '')) = LOWER(?)
                  AND start_at = ? AND end_at = ?
                """,
                (title, start_at, end_at),
            ).fetchone()
        if row is None:
            return None
        return self._work_shift_from_row(row)

    def find_duplicate_assignment(self, title: str, due_at: str) -> Assignment | None:
        """Find existing assignment with same title and due_at."""

        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM assignments
                WHERE LOWER(title) = LOWER(?) AND due_at = ?
                """,
                (title, due_at),
            ).fetchone()
        if row is None:
            return None
        return self._assignment_from_row(row)

    def _insert_class_session(
        self,
        connection: sqlite3.Connection,
        values: tuple[object, ...],
    ) -> None:
        connection.execute(
            """
            INSERT INTO class_sessions (
                id, module_id, title, weekday, start_time, end_time, location,
                recurrence, active, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    def _module_from_row(self, row: sqlite3.Row) -> StudyModule:
        return StudyModule(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            lecturer=row["lecturer"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _class_session_from_row(self, row: sqlite3.Row) -> ClassSession:
        module_id = row["module_id"] or None
        return ClassSession(
            id=row["id"],
            module_id=module_id,
            title=row["title"],
            weekday=int(row["weekday"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"],
            recurrence=row["recurrence"] or "weekly",
            active=bool(row["active"]),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _work_shift_from_row(self, row: sqlite3.Row) -> WorkShift:
        if row["start_at"] and row["end_at"]:
            start_at = ensure_local_datetime(
                datetime.fromisoformat(row["start_at"]),
                self.timezone,
            )
            end_at = ensure_local_datetime(
                datetime.fromisoformat(row["end_at"]),
                self.timezone,
            )
        else:
            start_at = datetime.combine(
                date.fromisoformat(row["date"]),
                parse_hhmm(row["start_time"]),
                tzinfo=self.timezone,
            )
            end_at = datetime.combine(
                date.fromisoformat(row["date"]),
                parse_hhmm(row["end_time"]),
                tzinfo=self.timezone,
            )
            if end_at <= start_at:
                end_at = datetime.combine(
                    date.fromisoformat(row["date"]),
                    time(23, 59),
                    tzinfo=self.timezone,
                )
        return WorkShift(
            id=row["id"],
            title=row["title"] or row["workplace"] or "Work shift",
            start_at=start_at,
            end_at=end_at,
            location=row["location"] or row["workplace"],
            role=row["role"],
            energy_cost=row["energy_cost"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _assignment_from_row(self, row: sqlite3.Row) -> Assignment:
        status = _assignment_status(row["status"])
        due_source = row["due_at"] or row["due_date"]
        due_at = parse_due_at(due_source, self.timezone)
        return Assignment(
            id=row["id"],
            module_id=row["module_id"],
            title=row["title"],
            due_at=due_at,
            status=status,
            priority=_priority_rank(row),
            weight=row["weight"],
            estimated_hours=row["estimated_hours"],
            completed_hours=row["completed_hours"] or 0,
            notes=row["notes"] or row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _priority_label(priority: int) -> str:
    if priority <= 1:
        return "critical"
    if priority == 2:
        return "high"
    if priority == 3:
        return "medium"
    return "low"


def _priority_rank(row: sqlite3.Row) -> int:
    if row["priority_rank"] is not None:
        return int(row["priority_rank"])
    return {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
    }.get(row["priority"], 3)


def _assignment_status(value: str) -> AssignmentStatus:
    mapping = {
        "not_started": AssignmentStatus.TODO,
        "graded": AssignmentStatus.DONE,
        "archived": AssignmentStatus.DONE,
    }
    if value in mapping:
        return mapping[value]
    try:
        return AssignmentStatus(value)
    except ValueError:
        return AssignmentStatus.TODO
