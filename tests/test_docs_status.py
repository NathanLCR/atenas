"""Documentation status guardrails."""

from __future__ import annotations

from pathlib import Path


def test_historical_superpowers_plans_have_status_notice() -> None:
    plan_paths = sorted(Path("docs/superpowers/plans").glob("*.md"))

    assert plan_paths
    for path in plan_paths:
        text = path.read_text(encoding="utf-8")
        assert "## Historical Plan Status" in text, path
        assert "archival" in text.lower(), path
