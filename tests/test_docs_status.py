"""Documentation status guardrails."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
DOCS_README = DOCS_DIR / "README.md"
CANONICAL_DOCS = (
    "GETTING_STARTED.md",
    "AGENT_LOOP.md",
    "PRODUCT_SPEC.md",
    "ARCHITECTURE.md",
    "AGENT_POLICY.md",
    "SECURITY.md",
    "REQUIREMENTS.md",
    "DATA_MODEL.md",
    "SCHEMAS.md",
    "CONTEXT_MANAGEMENT.md",
    "DECISIONS.md",
    "COMMAND_TOOL_PARITY.md",
)


def test_canonical_docs_listed_in_readme_exist_and_are_non_empty() -> None:
    readme_text = DOCS_README.read_text(encoding="utf-8")
    for filename in CANONICAL_DOCS:
        assert filename in readme_text, filename
        doc_path = DOCS_DIR / filename
        assert doc_path.is_file(), doc_path
        assert doc_path.read_text(encoding="utf-8").strip(), doc_path


def test_tracked_docs_do_not_reference_ignored_superpowers_dir() -> None:
    for doc_path in sorted(DOCS_DIR.glob("*.md")):
        content = doc_path.read_text(encoding="utf-8")
        assert "docs/superpowers/" not in content, doc_path
