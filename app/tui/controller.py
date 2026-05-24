"""State machine for the Atenas terminal UI."""

from __future__ import annotations

from dataclasses import dataclass

from app.tui.models import DEFAULT_TABS, TuiView
from app.tui.view_model import TuiContext, load_view


@dataclass
class TuiController:
    """Hold active tab and search state without depending on curses."""

    context: TuiContext
    tabs: tuple[tuple[str, str], ...] = DEFAULT_TABS
    active_index: int = 0
    search_query: str = ""
    status_message: str = "1-8 tabs | arrows move | / search | r refresh | q quit"

    @property
    def active_key(self) -> str:
        return self.tabs[self.active_index][0]

    def current_view(self) -> TuiView:
        return load_view(self.context, self.active_key, search_query=self.search_query)

    def handle_command(self, command: str) -> bool:
        if command == "quit":
            return False
        if command == "next_tab":
            self.active_index = (self.active_index + 1) % len(self.tabs)
            self.status_message = self._tab_status()
            return True
        if command == "previous_tab":
            self.active_index = (self.active_index - 1) % len(self.tabs)
            self.status_message = self._tab_status()
            return True
        if command == "refresh":
            self.status_message = "Refreshed."
            return True
        if command.startswith("tab:"):
            self._set_active_key(command.removeprefix("tab:"))
            return True
        return True

    def set_search_query(self, query: str) -> None:
        self.search_query = query.strip()
        self._set_active_key("search")
        if self.search_query:
            self.status_message = f'Search: "{self.search_query}"'
        else:
            self.status_message = "Search cleared."

    def _set_active_key(self, key: str) -> None:
        for index, (tab_key, label) in enumerate(self.tabs):
            if tab_key == key:
                self.active_index = index
                self.status_message = f"Tab: {label}"
                return
        self.status_message = f"Unknown tab: {key}"

    def _tab_status(self) -> str:
        return f"Tab: {self.tabs[self.active_index][1]}"
