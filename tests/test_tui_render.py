from app.tui.models import TuiRow, TuiSection, TuiView
from app.tui.render import render_view


def test_render_view_includes_tabs_and_sections() -> None:
    view = TuiView(
        key="today",
        title="Today",
        subtitle="Thu 21 May",
        sections=(
            TuiSection(
                title="Deadlines",
                rows=(
                    TuiRow(("NLP CA1", "due 23:59")),
                ),
            ),
        ),
    )

    lines = render_view(
        view,
        tabs=(("home", "Home"), ("today", "Today")),
        active_key="today",
        width=60,
        height=12,
        status="q quit",
    )

    joined = "\n".join(lines)
    assert "[Today]" in joined
    assert "Thu 21 May" in joined
    assert "Deadlines" in joined
    assert "NLP CA1" in joined
    assert "q quit" in lines[-1]


def test_render_view_clips_to_dimensions() -> None:
    view = TuiView(
        key="knowledge",
        title="Knowledge",
        sections=(
            TuiSection(
                title="Notes",
                rows=tuple(TuiRow((f"Long note title {index}", "manual")) for index in range(20)),
            ),
        ),
    )

    lines = render_view(
        view,
        tabs=(("knowledge", "Knowledge"),),
        active_key="knowledge",
        width=24,
        height=8,
        status="ready",
    )

    assert len(lines) == 8
    assert all(len(line) <= 24 for line in lines)
    assert lines[-1].strip() == "ready"
