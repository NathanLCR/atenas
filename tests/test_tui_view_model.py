from pathlib import Path

from app.config import Settings
from app.tui.view_model import build_tui_context, load_view
from core.academic.service import AcademicService
from core.db import init_db
from core.knowledge.service import KnowledgeService


def test_home_view_summarizes_runtime_state(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    AcademicService(settings.db_path, timezone=settings.timezone).add_module(
        name="Deep Learning",
        code="DL",
    )

    context = build_tui_context(settings)
    view = load_view(context, "home")

    text = _view_text(view)
    assert view.title == "Atenas"
    assert "Modules" in text
    assert "1" in text
    assert str(settings.db_path) in text


def test_home_view_labels_limited_knowledge_counts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    for index in range(6):
        service.create_note(title=f"Note {index}", body="Body")
        file_path = settings.inbox_dir / f"brief-{index}.txt"
        file_path.write_text("Brief", encoding="utf-8")
        service.register_file(str(file_path), title=f"Brief {index}")

    context = build_tui_context(settings)
    view = load_view(context, "home")

    text = _view_text(view)
    assert "Latest notes 5 shown" in text
    assert "Latest files 5 shown" in text


def test_deadlines_view_lists_open_assignments(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    service.add_assignment(
        title="NLP CA1",
        due_at="2026-05-22 23:59",
        priority=2,
        estimated_hours=4,
    )

    context = build_tui_context(settings)
    view = load_view(context, "deadlines")

    text = _view_text(view)
    assert "NLP CA1" in text
    assert "priority 2" in text


def test_knowledge_view_lists_notes_and_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    file_path = settings.inbox_dir / "cnn.pdf"
    file_path.write_text("Convolution notes", encoding="utf-8")
    service = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    service.create_note(title="CNN notes", body="Convolutions and pooling", tags=["ml"])
    service.register_file(str(file_path), title="CNN brief", tags=["ml"])

    context = build_tui_context(settings)
    view = load_view(context, "knowledge")

    text = _view_text(view)
    assert "CNN notes" in text
    assert "CNN brief" in text
    assert "ml" in text


def test_search_view_uses_local_keyword_search(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)
    service = KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
    service.create_note(title="Transformers", body="Attention layers and embeddings")

    context = build_tui_context(settings)
    view = load_view(context, "search", search_query="attention")

    text = _view_text(view)
    assert "Transformers" in text
    assert "attention" in view.subtitle.lower()


def test_unknown_view_falls_back_to_home(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    init_db(settings.db_path)

    context = build_tui_context(settings)
    view = load_view(context, "nope")

    assert view.key == "home"


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


def _view_text(view) -> str:
    return "\n".join(
        " ".join(row.cells)
        for section in view.sections
        for row in section.rows
    )
