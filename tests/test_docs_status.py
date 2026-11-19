"""Documentation status guardrails."""

from __future__ import annotations

from pathlib import Path

DOCS_README = Path("docs/README.md")


def test_docs_do_not_link_to_untracked_local_notes() -> None:
    for path in [DOCS_README, *sorted(Path("docs").glob("*.md"))]:
        assert "docs/superpowers" not in path.read_text(encoding="utf-8"), path
