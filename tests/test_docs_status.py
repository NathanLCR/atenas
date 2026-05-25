"""Documentation status guardrails."""

from __future__ import annotations

from pathlib import Path


SUPERPOWERS_README = Path("docs/superpowers/README.md")
DOCS_README = Path("docs/README.md")


def test_historical_superpowers_plans_have_status_notice() -> None:
    plan_paths = sorted(Path("docs/superpowers/plans").glob("*.md"))

    assert plan_paths
    for path in plan_paths:
        text = path.read_text(encoding="utf-8")
        assert "## Historical Plan Status" in text, path
        assert "archival" in text.lower(), path


def test_superpowers_readme_is_live_roadmap() -> None:
    text = SUPERPOWERS_README.read_text(encoding="utf-8")
    lower = text.lower()

    assert "# atenas superpowers roadmap" in lower
    assert "live roadmap" in lower
    assert "pending-action ux" in lower
    assert "`/pending`" in text
    assert "`/cancel_pending`" in text


def test_superpowers_readme_names_archival_plans() -> None:
    text = SUPERPOWERS_README.read_text(encoding="utf-8")
    lower = text.lower()

    assert "archival" in lower
    for path in sorted(Path("docs/superpowers/plans").glob("*.md")):
        assert f"`{path.as_posix()}`" in text


def test_canonical_docs_index_points_to_superpowers_roadmap() -> None:
    text = DOCS_README.read_text(encoding="utf-8")

    assert "## Superpowers roadmap" in text
    assert "`docs/superpowers/README.md`" in text
