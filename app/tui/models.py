"""Display models for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiRow:
    """A single display row inside a section."""

    cells: tuple[str, ...]
    emphasis: bool = False


@dataclass(frozen=True)
class TuiSection:
    """A titled group of rows."""

    title: str
    rows: tuple[TuiRow, ...] = ()
    empty_message: str = "Nothing to show."


@dataclass(frozen=True)
class TuiView:
    """One full-screen TUI tab."""

    key: str
    title: str
    subtitle: str = ""
    sections: tuple[TuiSection, ...] = ()
    empty_message: str = "Nothing to show."


DEFAULT_TABS: tuple[tuple[str, str], ...] = (
    ("home", "Home"),
    ("today", "Today"),
    ("week", "Week"),
    ("plan", "Plan"),
    ("deadlines", "Deadlines"),
    ("data", "Data"),
    ("knowledge", "Knowledge"),
    ("search", "Search"),
)
