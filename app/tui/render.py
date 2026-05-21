"""Pure text rendering for the Atenas terminal UI."""

from __future__ import annotations

from app.tui.models import TuiRow, TuiSection, TuiView

MIN_WIDTH = 32
MIN_HEIGHT = 6


def render_view(
    view: TuiView,
    *,
    tabs: tuple[tuple[str, str], ...],
    active_key: str,
    width: int,
    height: int,
    status: str,
) -> list[str]:
    """Render a TUI view into clipped terminal lines."""

    width = max(1, width)
    height = max(1, height)
    body_height = height - 1
    lines: list[str] = [
        _tab_bar(tabs, active_key),
        _rule(width),
        view.title if not view.subtitle else f"{view.title} - {view.subtitle}",
        "",
    ]

    if view.sections:
        for section in view.sections:
            _append_section(lines, section)
    else:
        lines.append(view.empty_message)

    clipped_body = [_clip(line, width) for line in lines[:body_height]]
    while len(clipped_body) < body_height:
        clipped_body.append("")
    return [*clipped_body, _clip(status, width)]


def _append_section(lines: list[str], section: TuiSection) -> None:
    lines.append(section.title)
    if not section.rows:
        lines.append(f"  {section.empty_message}")
        lines.append("")
        return
    for row in section.rows:
        lines.append(_row_text(row))
    lines.append("")


def _row_text(row: TuiRow) -> str:
    prefix = "* " if row.emphasis else "  "
    return prefix + " | ".join(str(cell) for cell in row.cells)


def _tab_bar(tabs: tuple[tuple[str, str], ...], active_key: str) -> str:
    labels = []
    for key, label in tabs:
        labels.append(f"[{label}]" if key == active_key else label)
    return "  ".join(labels)


def _rule(width: int) -> str:
    return "-" * width


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"
