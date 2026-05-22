"""Curses runtime for the Atenas terminal UI."""

from __future__ import annotations

import curses

from app.config import Settings
from app.tui.controller import TuiController
from app.tui.models import DEFAULT_TABS
from app.tui.render import render_view
from app.tui.view_model import build_tui_context


def run(settings: Settings | None = None) -> None:
    """Run the terminal UI."""

    context = build_tui_context(settings)
    controller = TuiController(context)
    curses.wrapper(lambda stdscr: _run_loop(stdscr, controller))


def command_from_key(key: int) -> str:
    """Map a curses key code to a controller command."""

    if key in (ord("q"), ord("Q")):
        return "quit"
    if key in (ord("r"), ord("R")):
        return "refresh"
    if key == ord("/"):
        return "search_prompt"
    if key in (curses.KEY_RIGHT, ord("l"), ord("L")):
        return "next_tab"
    if key in (curses.KEY_LEFT, ord("h"), ord("H")):
        return "previous_tab"
    if ord("1") <= key <= ord(str(len(DEFAULT_TABS))):
        index = key - ord("1")
        return f"tab:{DEFAULT_TABS[index][0]}"
    return "noop"


def _run_loop(stdscr, controller: TuiController) -> None:
    _set_cursor_visibility(False)
    stdscr.keypad(True)
    while True:
        _draw(stdscr, controller)
        key = stdscr.getch()
        command = command_from_key(key)
        if command == "search_prompt":
            controller.set_search_query(_prompt(stdscr, "Search notes/files"))
            continue
        keep_running = controller.handle_command(command)
        if not keep_running:
            break


def _draw(stdscr, controller: TuiController) -> None:
    height, width = stdscr.getmaxyx()
    lines = render_view(
        controller.current_view(),
        tabs=controller.tabs,
        active_key=controller.active_key,
        width=width,
        height=height,
        status=controller.status_message,
    )
    stdscr.erase()
    for row, line in enumerate(lines):
        if row >= height:
            break
        stdscr.addnstr(row, 0, line, max(0, width - 1))
    stdscr.refresh()


def _prompt(stdscr, label: str) -> str:
    height, width = stdscr.getmaxyx()
    prompt = f"{label}: "
    _set_cursor_visibility(True)
    curses.echo()
    try:
        stdscr.move(max(0, height - 1), 0)
        stdscr.clrtoeol()
        stdscr.addnstr(max(0, height - 1), 0, prompt, max(0, width - 1))
        value = stdscr.getstr(max(0, height - 1), len(prompt), max(1, width - len(prompt) - 1))
    finally:
        curses.noecho()
        _set_cursor_visibility(False)
    return value.decode("utf-8", errors="replace").strip()


def _set_cursor_visibility(visible: bool) -> None:
    try:
        curses.curs_set(1 if visible else 0)
    except curses.error:
        pass
