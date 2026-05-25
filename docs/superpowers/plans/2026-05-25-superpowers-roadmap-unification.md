# Superpowers Roadmap Unification Implementation Plan

## Historical Plan Status

This is the active implementation plan while the roadmap unification slice is
being executed. After that implementation commit lands, treat this file as an
archival record; current phase status belongs in `docs/superpowers/README.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live Superpowers roadmap that separates current phase work from archival implementation plans.

**Architecture:** Keep canonical product docs in `docs/`. Add `docs/superpowers/README.md` as the live roadmap for Superpowers specs, historical plans, phase status, big-file refactor support, and cut candidates. Guard it with documentation tests so the roadmap remains explicit when future phases are added.

**Tech Stack:** Markdown, pytest, Python standard library `pathlib`.

---

### Task 1: Roadmap Guardrail Tests

**Files:**
- Modify: `tests/test_docs_status.py`

- [ ] **Step 1: Add failing roadmap tests**

Replace `tests/test_docs_status.py` with:

```python
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
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_docs_status.py -q
```

Expected: failure because `docs/superpowers/README.md` does not exist yet.

### Task 2: Live Superpowers Roadmap

**Files:**
- Create: `docs/superpowers/README.md`

- [ ] **Step 1: Add the roadmap document**

Create `docs/superpowers/README.md` with:

```markdown
# Atenas Superpowers Roadmap

## Status

This is the live roadmap for Superpowers-driven Atenas work. Canonical product
contracts still live in `docs/README.md` and the canonical docs listed there.
This file only answers: which Superpowers specs and phases are current, which
plans are archival, what comes next, and which refactors support that work.

## How To Read This Folder

- `docs/superpowers/README.md` is the live roadmap.
- `docs/superpowers/specs/*.md` are design records. Some remain current, but
  implementation status is summarized here.
- `docs/superpowers/plans/*.md` are archival implementation records. Their
  unchecked boxes preserve original task breakdowns, not current project state.

Archival plans:

- `docs/superpowers/plans/2026-05-21-atenas-audit-hardening.md`
- `docs/superpowers/plans/2026-05-21-atenas-tui.md`
- `docs/superpowers/plans/2026-05-24-hermes-inspired-agent-hardening.md`
- `docs/superpowers/plans/2026-05-24-local-model-agent-runtime-state.md`
- `docs/superpowers/plans/2026-05-25-superpowers-roadmap-unification.md`

## Phase Status

| Phase | Status | Source | Current note |
|---|---|---|---|
| v1 gap and packaging closure | Done | `docs/superpowers/specs/2026-05-24-atenas-v1-gap-and-packaging-spec.md` | Package discovery, planning acceptance, parity audit, doc drift cleanup, and v1 tool coverage are implemented and tested. |
| Durable pending-action storage base | Done | `docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md` | `core/nl/runtime_state.py` persists threads and pending actions; Telegram `yes` and `no` can resolve durable pending actions. |
| Pending-action UX | Partial | `docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md` | Durable confirmation exists, but deterministic `/pending` and `/cancel_pending` commands are not registered yet. |
| Toolsets | Done | `docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md` | `core/nl/toolsets.py` groups safe, egress, destructive, readonly, and dev-local tools; the agent loop filters visible tools by selected toolsets. |
| Backup and restore | Done | `docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md` | `core/backup.py` and `atenas backup`/`atenas restore` exist with tests. |
| Local model profile config | Next | Runtime state and Hermes specs | Add explicit context length, timeout, prompt limits, and doctor output. |
| Budgeted prompt assembly and tighter tool selection | Next | Runtime state spec | Extract prompt assembly from `core/nl/agent.py`, enforce model-profile budgets, and record selection metadata. |
| Trace replay and search | Next | Runtime state and Hermes specs | Extend trace inspection without rerunning writes or exposing full prompts by default. |
| Approved skill memory | Later | Hermes spec | Store reviewed procedural memories as context only; never grant permissions. |
| Channel adapter boundary | Later | Hermes spec | Extract only when a second channel is actually scoped. |

## Refactor Support

Large files should be split as they are touched by the next phases:

- `app/bot.py`: split into Telegram application wiring, NL confirmation flow,
  academic commands, knowledge/retrieval commands, LLM note commands,
  notification jobs, and shared formatting.
- `core/nl/tools.py`: split into registry mechanics, tool definitions,
  academic handlers, knowledge/retrieval handlers, memory handlers, web
  handlers, and action execution helpers.
- `core/nl/router.py` and `core/nl/classifier.py`: keep quarantined as legacy
  compatibility until tests and public imports are migrated to the tool loop.
- `core/academic/service.py`, `core/academic/importers.py`, and
  `core/academic/repository.py`: split only when adding or changing academic
  behavior, so repository/service boundaries stay clear.

## Cut Candidates

- Do not add new product behavior to `NLRouter` or `NLClassifier`; they are
  legacy compatibility surfaces.
- Do not create new live checklist docs under `docs/superpowers/plans/`.
  Historical plans remain archival records.
- Keep generated local state, dependency caches, `.env`, SQLite files, logs,
  inbox contents, and output artifacts ignored as runtime data.
- Do not delete historical specs or plans just to reduce file count; preserve
  them as records and point readers to this roadmap for current state.

## Next Recommended Slice

Implement pending-action UX: add `/pending` and `/cancel_pending` Telegram
commands backed by `AgentRuntimeStore`, then update tests and docs. This closes
the partial runtime-state phase before model profile and prompt-budget work.
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
.venv/bin/pytest tests/test_docs_status.py -q
```

Expected: tests still fail until `docs/README.md` links the roadmap if Task 3
has not been completed.

### Task 3: Canonical Docs Index Link And Snapshot Coherence

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/AGENT_LOOP.md`

- [ ] **Step 1: Add the Superpowers roadmap pointer**

In `docs/README.md`, after the "Current gap spec" section, add:

```markdown
## Superpowers roadmap

Superpowers implementation status is summarized in
`docs/superpowers/README.md`. Use that roadmap to distinguish live phase work
from archival implementation plans before starting new hardening or refactor
work.
```

- [ ] **Step 2: Run focused docs tests**

In `docs/AGENT_LOOP.md`, update the "Current Implementation State" paragraph
so it says pending confirm-first actions are stored in SQLite through
`AgentRuntimeStore`, with Telegram `user_data` used only as a process-lifetime
speed cache.

- [ ] **Step 3: Run focused docs tests**

Run:

```bash
.venv/bin/pytest tests/test_docs_status.py -q
```

Expected: all docs status tests pass.

### Task 4: Verification And Commit

**Files:**
- Modify: `tests/test_docs_status.py`
- Create: `docs/superpowers/README.md`
- Modify: `docs/README.md`
- Modify: `docs/AGENT_LOOP.md`

- [ ] **Step 1: Run the full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: full suite passes. A pytest-asyncio deprecation warning may appear;
it is pre-existing and not part of this slice.

- [ ] **Step 2: Review git diff**

Run:

```bash
git diff -- tests/test_docs_status.py docs/superpowers/README.md docs/README.md docs/AGENT_LOOP.md
```

Expected: only the docs roadmap, docs index pointer, agent-loop implementation
snapshot correction, and docs guardrail tests changed.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add tests/test_docs_status.py docs/superpowers/README.md docs/README.md docs/AGENT_LOOP.md
git commit -m "docs: add live superpowers roadmap"
```

Expected: one implementation commit after the design-doc commit.
