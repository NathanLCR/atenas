"""Deterministic CSV/JSON importers for Phase 5 academic data."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from core.academic.service import AcademicService
from core.academic.validators import (
    parse_datetime_input,
    parse_datetime_strict,
    parse_weekday,
    validate_energy_cost,
    validate_hours,
    validate_notes,
    validate_priority,
    validate_status,
    validate_text_field,
    validate_weight,
)
from core.time import parse_due_at


@dataclass(frozen=True)
class ImportResult:
    """Summary of an import operation."""

    parsed: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)


def import_assignments_csv(
    file_path: Path | str,
    service: AcademicService,
    dry_run: bool = True,
) -> ImportResult:
    """Import assignments from a CSV file.

    Required columns: title, due_at
    Optional: module_id, priority, status, weight, estimated_hours, completed_hours, notes
    """
    file_path = Path(file_path)
    result = ImportResult()

    if not file_path.exists():
        return ImportResult(errors=1, error_details=[f"File not found: {file_path}"])

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ImportResult(errors=1, error_details=["CSV file is empty or has no header"])

        missing = _check_required_columns(reader.fieldnames, ["title", "due_at"])
        if missing:
            return ImportResult(errors=1, error_details=[f"Missing required columns: {', '.join(missing)}"])

        for row_num, row in enumerate(reader, start=2):
            result = _process_assignment_row(row, row_num, result, service, dry_run)

    return result


def _process_assignment_row(
    row: dict[str, str],
    row_num: int,
    result: ImportResult,
    service: AcademicService,
    dry_run: bool,
) -> ImportResult:
    result = ImportResult(
        parsed=result.parsed + 1,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        error_details=list(result.error_details),
    )

    title = row.get("title", "").strip()
    if not title:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: title is required"],
        )

    due_raw = row.get("due_at", "").strip()
    if not due_raw:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: due_at is required"],
        )

    parsed_due, err = parse_datetime_input(due_raw, service.timezone)
    if err:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: {err}"],
        )

    module_id = row.get("module_id", "").strip() or None

    priority_raw = row.get("priority", "3").strip()
    priority = int(priority_raw) if priority_raw.isdigit() else 3
    if validate_priority(priority) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: priority must be between 1 and 5"],
        )

    status = row.get("status", "todo").strip()
    if validate_status(status) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: invalid status '{status}'"],
        )

    weight_raw = row.get("weight", "").strip()
    weight = float(weight_raw) if weight_raw else None
    if weight is not None and validate_weight(weight) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: weight must be between 0 and 100"],
        )

    est_raw = row.get("estimated_hours", "").strip()
    estimated = float(est_raw) if est_raw else None
    if estimated is not None and validate_hours(estimated) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: estimated_hours must be >= 0"],
        )

    comp_raw = row.get("completed_hours", "0").strip()
    completed = float(comp_raw) if comp_raw else 0
    if validate_hours(completed) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: completed_hours must be >= 0"],
        )

    notes = validate_notes(row.get("notes"))

    if dry_run:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )

    cmd_result = service.add_assignment(
        title=title,
        due_at=parsed_due,
        module_id=module_id,
        priority=priority,
        status=status,
        weight=weight,
        estimated_hours=estimated,
        completed_hours=completed,
        notes=notes,
    )
    if cmd_result.success:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )
    if "already exists" in cmd_result.message.lower():
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped + 1,
            errors=result.errors,
            error_details=[*result.error_details, f"Row {row_num}: duplicate skipped — {title}"],
        )
    return ImportResult(
        parsed=result.parsed,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors + 1,
        error_details=[*result.error_details, f"Row {row_num}: {cmd_result.message}"],
    )


def import_work_shifts_csv(
    file_path: Path | str,
    service: AcademicService,
    dry_run: bool = True,
) -> ImportResult:
    """Import work shifts from a CSV file.

    Required columns: start_at, end_at
    Optional: title, location, role, energy_cost, notes
    """
    file_path = Path(file_path)
    result = ImportResult()

    if not file_path.exists():
        return ImportResult(errors=1, error_details=[f"File not found: {file_path}"])

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ImportResult(errors=1, error_details=["CSV file is empty or has no header"])

        missing = _check_required_columns(reader.fieldnames, ["start_at", "end_at"])
        if missing:
            return ImportResult(errors=1, error_details=[f"Missing required columns: {', '.join(missing)}"])

        for row_num, row in enumerate(reader, start=2):
            result = _process_shift_row(row, row_num, result, service, dry_run)

    return result


def _process_shift_row(
    row: dict[str, str],
    row_num: int,
    result: ImportResult,
    service: AcademicService,
    dry_run: bool,
) -> ImportResult:
    result = ImportResult(
        parsed=result.parsed + 1,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        error_details=list(result.error_details),
    )

    start_raw = row.get("start_at", "").strip()
    end_raw = row.get("end_at", "").strip()

    if not start_raw:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: start_at is required"],
        )
    if not end_raw:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: end_at is required"],
        )

    parsed_start, err = parse_datetime_strict(start_raw, service.timezone)
    if err:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: {err}"],
        )

    parsed_end, err = parse_datetime_strict(end_raw, service.timezone)
    if err:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: {err}"],
        )

    title = row.get("title", "").strip() or "Work"

    energy_raw = row.get("energy_cost", "").strip()
    energy = int(energy_raw) if energy_raw else None
    if energy is not None and validate_energy_cost(energy) is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: energy_cost must be between 1 and 5"],
        )

    location = validate_text_field(row.get("location"), max_length=200)
    role = validate_text_field(row.get("role"), max_length=100)
    notes = validate_notes(row.get("notes"))

    if dry_run:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )

    cmd_result = service.add_work_shift(
        title=title,
        start_at=parsed_start,
        end_at=parsed_end,
        location=location,
        role=role,
        energy_cost=energy,
        notes=notes,
    )
    if cmd_result.success:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )
    if "already exists" in cmd_result.message.lower():
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped + 1,
            errors=result.errors,
            error_details=[*result.error_details, f"Row {row_num}: duplicate skipped — {title}"],
        )
    return ImportResult(
        parsed=result.parsed,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors + 1,
        error_details=[*result.error_details, f"Row {row_num}: {cmd_result.message}"],
    )


def import_modules_csv(
    file_path: Path | str,
    service: AcademicService,
    dry_run: bool = True,
) -> ImportResult:
    """Import modules from a CSV file.

    Required columns: name
    Optional: code, lecturer, notes
    """
    file_path = Path(file_path)
    result = ImportResult()

    if not file_path.exists():
        return ImportResult(errors=1, error_details=[f"File not found: {file_path}"])

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ImportResult(errors=1, error_details=["CSV file is empty or has no header"])

        missing = _check_required_columns(reader.fieldnames, ["name"])
        if missing:
            return ImportResult(errors=1, error_details=[f"Missing required columns: {', '.join(missing)}"])

        for row_num, row in enumerate(reader, start=2):
            result = _process_module_row(row, row_num, result, service, dry_run)

    return result


def _process_module_row(
    row: dict[str, str],
    row_num: int,
    result: ImportResult,
    service: AcademicService,
    dry_run: bool,
) -> ImportResult:
    result = ImportResult(
        parsed=result.parsed + 1,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        error_details=list(result.error_details),
    )

    name = row.get("name", "").strip()
    if not name:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: name is required"],
        )

    code = validate_text_field(row.get("code"), max_length=50)
    lecturer = validate_text_field(row.get("lecturer"), max_length=100)
    notes = validate_notes(row.get("notes"))

    if dry_run:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )

    cmd_result = service.add_module(name=name, code=code, lecturer=lecturer, notes=notes)
    if cmd_result.success:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )
    if "already exists" in cmd_result.message.lower():
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped + 1,
            errors=result.errors,
            error_details=[*result.error_details, f"Row {row_num}: duplicate skipped — {name}"],
        )
    return ImportResult(
        parsed=result.parsed,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors + 1,
        error_details=[*result.error_details, f"Row {row_num}: {cmd_result.message}"],
    )


def import_class_sessions_csv(
    file_path: Path | str,
    service: AcademicService,
    dry_run: bool = True,
) -> ImportResult:
    """Import class sessions from a CSV file.

    Required columns: title, weekday, start_time, end_time
    Optional: module_id, location, notes
    """
    file_path = Path(file_path)
    result = ImportResult()

    if not file_path.exists():
        return ImportResult(errors=1, error_details=[f"File not found: {file_path}"])

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ImportResult(errors=1, error_details=["CSV file is empty or has no header"])

        missing = _check_required_columns(reader.fieldnames, ["title", "weekday", "start_time", "end_time"])
        if missing:
            return ImportResult(errors=1, error_details=[f"Missing required columns: {', '.join(missing)}"])

        for row_num, row in enumerate(reader, start=2):
            result = _process_class_row(row, row_num, result, service, dry_run)

    return result


def _process_class_row(
    row: dict[str, str],
    row_num: int,
    result: ImportResult,
    service: AcademicService,
    dry_run: bool,
) -> ImportResult:
    result = ImportResult(
        parsed=result.parsed + 1,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        error_details=list(result.error_details),
    )

    title = row.get("title", "").strip()
    if not title:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: title is required"],
        )

    weekday = parse_weekday(row.get("weekday", "").strip())
    if weekday is None:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: invalid weekday"],
        )

    start_time = row.get("start_time", "").strip()
    end_time = row.get("end_time", "").strip()
    if not start_time or not end_time:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: start_time and end_time are required"],
        )

    from core.time import parse_hhmm
    try:
        if parse_hhmm(start_time) >= parse_hhmm(end_time):
            return ImportResult(
                parsed=result.parsed,
                created=result.created,
                skipped=result.skipped,
                errors=result.errors + 1,
                error_details=[*result.error_details, f"Row {row_num}: start_time must be before end_time"],
            )
    except ValueError:
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped,
            errors=result.errors + 1,
            error_details=[*result.error_details, f"Row {row_num}: invalid time format"],
        )

    module_id = row.get("module_id", "").strip() or None
    location = validate_text_field(row.get("location"), max_length=200)
    notes = validate_notes(row.get("notes"))

    if dry_run:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )

    cmd_result = service.add_class_session(
        title=title,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        module_id=module_id,
        location=location,
        notes=notes,
    )
    if cmd_result.success:
        return ImportResult(
            parsed=result.parsed,
            created=result.created + 1,
            skipped=result.skipped,
            errors=result.errors,
            error_details=result.error_details,
        )
    if "already exists" in cmd_result.message.lower():
        return ImportResult(
            parsed=result.parsed,
            created=result.created,
            skipped=result.skipped + 1,
            errors=result.errors,
            error_details=[*result.error_details, f"Row {row_num}: duplicate skipped — {title}"],
        )
    return ImportResult(
        parsed=result.parsed,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors + 1,
        error_details=[*result.error_details, f"Row {row_num}: {cmd_result.message}"],
    )


def import_json_bundle(
    file_path: Path | str,
    service: AcademicService,
    dry_run: bool = True,
) -> ImportResult:
    """Import all entities from a JSON bundle file."""
    file_path = Path(file_path)
    result = ImportResult()

    if not file_path.exists():
        return ImportResult(errors=1, error_details=[f"File not found: {file_path}"])

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return ImportResult(errors=1, error_details=[f"Invalid JSON: {exc}"])

    for module_data in data.get("modules", []):
        result = _process_module_row(module_data, result.parsed + 1, result, service, dry_run)

    for class_data in data.get("class_sessions", []):
        result = _process_class_row(class_data, result.parsed + 1, result, service, dry_run)

    for shift_data in data.get("work_shifts", []):
        result = _process_shift_row(shift_data, result.parsed + 1, result, service, dry_run)

    for assignment_data in data.get("assignments", []):
        result = _process_assignment_row(assignment_data, result.parsed + 1, result, service, dry_run)

    return result


def _check_required_columns(fieldnames: list[str], required: list[str]) -> list[str]:
    """Return list of missing required columns."""
    return [col for col in required if col not in fieldnames]


def format_import_result(result: ImportResult, dry_run: bool) -> str:
    """Format import result for display."""
    prefix = "Dry run" if dry_run else "Import"
    lines = [
        f"{prefix} complete",
        "",
        f"Parsed: {result.parsed}",
        f"Created: {result.created}",
        f"Skipped duplicates: {result.skipped}",
        f"Errors: {result.errors}",
    ]
    if result.error_details:
        lines.append("")
        lines.extend(result.error_details)
    return "\n".join(lines)


def main() -> None:
    """CLI entry point for imports."""
    import argparse

    parser = argparse.ArgumentParser(description="Import academic data into Atenas")
    parser.add_argument("entity", choices=["assignments", "work_shifts", "modules", "class_sessions", "json"])
    parser.add_argument("file", help="Path to CSV or JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without making changes")
    parser.add_argument("--apply", action="store_true", help="Apply changes to database")
    parser.add_argument("--db", default="data/atenas.sqlite", help="Database path")
    parser.add_argument("--timezone", default="Europe/Dublin", help="Timezone")

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply")
        sys.exit(1)

    dry_run = args.dry_run
    service = AcademicService(args.db, timezone=args.timezone)

    if args.entity == "assignments":
        result = import_assignments_csv(args.file, service, dry_run=dry_run)
    elif args.entity == "work_shifts":
        result = import_work_shifts_csv(args.file, service, dry_run=dry_run)
    elif args.entity == "modules":
        result = import_modules_csv(args.file, service, dry_run=dry_run)
    elif args.entity == "class_sessions":
        result = import_class_sessions_csv(args.file, service, dry_run=dry_run)
    elif args.entity == "json":
        result = import_json_bundle(args.file, service, dry_run=dry_run)
    else:
        print(f"Unknown entity: {args.entity}")
        sys.exit(1)

    print(format_import_result(result, dry_run))
    if result.errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
