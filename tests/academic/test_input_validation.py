"""Tests for Phase 5 validation and parsing utilities."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.academic.validators import (
    parse_date_only,
    parse_datetime_input,
    parse_datetime_strict,
    parse_kv_args,
    parse_weekday,
    validate_energy_cost,
    validate_hours,
    validate_notes,
    validate_priority,
    validate_status,
    validate_text_field,
    validate_weight,
)

TZ = ZoneInfo("Europe/Dublin")


class TestParseKvArgs:
    def test_simple_key_value(self) -> None:
        assert parse_kv_args("key=value") == {"key": "value"}

    def test_quoted_value(self) -> None:
        assert parse_kv_args('name="Deep Learning"') == {"name": "Deep Learning"}

    def test_multiple_args(self) -> None:
        result = parse_kv_args('title="NLP CA1" due="2026-05-21" priority=2')
        assert result == {"title": "NLP CA1", "due": "2026-05-21", "priority": "2"}

    def test_keys_are_lowercased(self) -> None:
        assert parse_kv_args("Name=Test") == {"name": "Test"}

    def test_empty_string(self) -> None:
        assert parse_kv_args("") == {}

    def test_quoted_value_with_spaces(self) -> None:
        assert parse_kv_args('location="Room 101"') == {"location": "Room 101"}


class TestParseWeekday:
    @pytest.mark.parametrize("alias,expected", [
        ("mon", 0), ("monday", 0), ("tue", 1), ("tuesday", 1),
        ("wed", 2), ("wednesday", 2), ("thu", 3), ("thursday", 3),
        ("fri", 4), ("friday", 4), ("sat", 5), ("saturday", 5),
        ("sun", 6), ("sunday", 6),
    ])
    def test_weekday_aliases(self, alias: str, expected: int) -> None:
        assert parse_weekday(alias) == expected

    @pytest.mark.parametrize("value,expected", [
        (0, 0), (1, 1), (6, 6),
    ])
    def test_weekday_integers(self, value: int, expected: int) -> None:
        assert parse_weekday(value) == expected

    def test_invalid_weekday_string(self) -> None:
        assert parse_weekday("xyz") is None

    def test_invalid_weekday_integer(self) -> None:
        assert parse_weekday(7) is None
        assert parse_weekday(-1) is None


class TestParseDatetimeInput:
    def test_full_datetime(self) -> None:
        dt, err = parse_datetime_input("2026-05-21 23:59", TZ)
        assert err is None
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.hour == 23
        assert dt.minute == 59

    def test_t_format(self) -> None:
        dt, err = parse_datetime_input("2026-05-21T14:00", TZ)
        assert err is None
        assert dt is not None
        assert dt.hour == 14

    def test_date_only_becomes_2359(self) -> None:
        dt, err = parse_datetime_input("2026-05-21", TZ)
        assert err is None
        assert dt is not None
        assert dt.hour == 23
        assert dt.minute == 59

    def test_invalid_datetime(self) -> None:
        dt, err = parse_datetime_input("not-a-date", TZ)
        assert dt is None
        assert err is not None


class TestParseDatetimeStrict:
    def test_full_datetime_accepted(self) -> None:
        dt, err = parse_datetime_strict("2026-05-21 16:00", TZ)
        assert err is None
        assert dt is not None

    def test_date_only_rejected(self) -> None:
        dt, err = parse_datetime_strict("2026-05-21", TZ)
        assert dt is None
        assert err is not None
        assert "Date-only not allowed" in err

    def test_invalid_rejected(self) -> None:
        dt, err = parse_datetime_strict("garbage", TZ)
        assert dt is None
        assert err is not None


class TestParseDateOnly:
    def test_valid_date(self) -> None:
        assert parse_date_only("2026-05-21", TZ) == date(2026, 5, 21)

    def test_invalid_date(self) -> None:
        assert parse_date_only("not-a-date", TZ) is None


class TestValidateStatus:
    @pytest.mark.parametrize("value", ["todo", "in_progress", "submitted", "done", "cancelled"])
    def test_valid_statuses(self, value: str) -> None:
        assert validate_status(value) == value

    def test_status_is_lowercased(self) -> None:
        assert validate_status("TODO") == "todo"

    def test_invalid_status(self) -> None:
        assert validate_status("unknown") is None


class TestValidatePriority:
    @pytest.mark.parametrize("value", [1, 2, 3, 4, 5, "1", "5"])
    def test_valid_priorities(self, value: str | int) -> None:
        assert validate_priority(value) is not None

    @pytest.mark.parametrize("value", [0, 6, -1, "abc"])
    def test_invalid_priorities(self, value: str | int) -> None:
        assert validate_priority(value) is None


class TestValidateHours:
    @pytest.mark.parametrize("value", [0, 1, 2.5, 1000, "3.5"])
    def test_valid_hours(self, value: str | float | int) -> None:
        assert validate_hours(value) is not None

    @pytest.mark.parametrize("value", [-1, 1001, "abc"])
    def test_invalid_hours(self, value: str | float | int) -> None:
        assert validate_hours(value) is None


class TestValidateWeight:
    def test_valid_weight(self) -> None:
        assert validate_weight(50) == 50.0
        assert validate_weight(0) == 0.0
        assert validate_weight(100) == 100.0

    def test_invalid_weight(self) -> None:
        assert validate_weight(-1) is None
        assert validate_weight(101) is None


class TestValidateEnergyCost:
    @pytest.mark.parametrize("value", [1, 2, 3, 4, 5])
    def test_valid_energy(self, value: int) -> None:
        assert validate_energy_cost(value) == value

    @pytest.mark.parametrize("value", [0, 6, -1, "abc"])
    def test_invalid_energy(self, value: int | str) -> None:
        assert validate_energy_cost(value) is None


class TestValidateTextField:
    def test_required_field_empty(self) -> None:
        assert validate_text_field("", required=True) == ""

    def test_required_field_none(self) -> None:
        assert validate_text_field(None, required=True) == ""

    def test_trims_whitespace(self) -> None:
        assert validate_text_field("  hello  ") == "hello"

    def test_exceeds_max_length(self) -> None:
        assert validate_text_field("a" * 201, max_length=200) is None

    def test_optional_none(self) -> None:
        assert validate_text_field(None) is None


class TestValidateNotes:
    def test_valid_notes(self) -> None:
        assert validate_notes("Some notes") == "Some notes"

    def test_empty_returns_none(self) -> None:
        assert validate_notes("") is None
        assert validate_notes("   ") is None
        assert validate_notes(None) is None

    def test_exceeds_max_length(self) -> None:
        assert validate_notes("a" * 2001) is None
