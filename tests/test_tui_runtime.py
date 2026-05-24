import curses

from app.tui.runtime import _set_cursor_visibility, command_from_key


def test_command_from_key_maps_quit() -> None:
    assert command_from_key(ord("q")) == "quit"
    assert command_from_key(ord("Q")) == "quit"


def test_command_from_key_maps_refresh_and_search() -> None:
    assert command_from_key(ord("r")) == "refresh"
    assert command_from_key(ord("/")) == "search_prompt"


def test_command_from_key_maps_numbered_tabs() -> None:
    assert command_from_key(ord("1")) == "tab:home"
    assert command_from_key(ord("4")) == "tab:plan"
    assert command_from_key(ord("8")) == "tab:search"


def test_command_from_key_ignores_unknown_key() -> None:
    assert command_from_key(ord("x")) == "noop"


def test_set_cursor_visibility_ignores_unsupported_terminals(monkeypatch) -> None:
    def unsupported_curs_set(_visibility: int) -> None:
        raise curses.error("curs_set() returned ERR")

    monkeypatch.setattr(curses, "curs_set", unsupported_curs_set)

    _set_cursor_visibility(False)
