from pathlib import Path

from app.config import Settings
from app.tui.controller import TuiController
from app.tui.models import DEFAULT_TABS
from app.tui.view_model import build_tui_context


def test_controller_starts_on_home(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.active_key == "home"
    assert controller.current_view().key == "home"


def test_controller_switches_tabs_by_command(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("tab:plan") is True

    assert controller.active_key == "plan"
    assert controller.current_view().key == "plan"


def test_controller_ignores_unknown_tab(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("tab:nope") is True

    assert controller.active_key == "home"
    assert "Unknown tab" in controller.status_message


def test_controller_search_sets_query_and_tab(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    controller.set_search_query("attention")

    assert controller.active_key == "search"
    assert controller.search_query == "attention"
    assert "attention" in controller.current_view().subtitle


def test_controller_quit_returns_false(tmp_path: Path) -> None:
    controller = TuiController(build_tui_context(_settings(tmp_path)))

    assert controller.handle_command("quit") is False


def test_default_tabs_are_number_addressable() -> None:
    assert len(DEFAULT_TABS) <= 9


def _settings(tmp_path: Path) -> Settings:
    inbox = tmp_path / "inbox"
    memory = tmp_path / "memory"
    inbox.mkdir()
    memory.mkdir()
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=memory,
        output_dir=tmp_path / "output",
        inbox_dir=inbox,
        logs_dir=tmp_path / "logs",
        knowledge_file_roots=[inbox, memory],
    )
