# Atenas v1 Gap And Packaging Spec

## Purpose

This spec defines the remaining work needed to make Atenas v1 match the
canonical product contract and fixes the editable-install failure reported when
running:

```bash
pip3 install -e .
```

The current codebase is test-green and already implements the core local,
Telegram-first posture, but the implementation is not yet fully aligned with
the v1 success criteria in `docs/PRODUCT_SPEC.md` and `docs/REQUIREMENTS.md`.

## Current Verified State

- Full test suite passed on 2026-05-24 with `561 passed`.
- Telegram slash commands cover status, schedule, planning, academic records,
  notes/files, retrieval, LLM study commands, reminders, and confirmations.
- Plain Telegram messages use `AgentLoop` and `ToolRegistry`.
- Destructive and egress agent tools create pending confirmations.
- Dashboard/API are guarded as local-only surfaces.
- Retrieval uses incremental sync and FTS5 with lexical fallback.
- CLI and TUI source code exist, but editable installation must work before
  the `atenas` console command is reliably available.

## Problem 1: v1 Feature Gap

The product spec says the LLM agent should be able to answer and act through
controlled tools for scheduling, planning, notes, retrieval, and data updates.
Today, many capabilities exist only as slash commands or service methods, while
the agent-facing `ToolRegistry` has a smaller tool catalog.

### Required Agent Tool Coverage

The v1 agent tool catalog must include read tools for:

- `get_status`
- `get_today_overview`
- `get_week_overview`
- `get_deadlines`
- `get_availability`
- `list_modules`
- `list_assignments`
- `list_class_sessions`
- `list_work_shifts`
- `search_notes`
- `retrieve_sources`
- `read_memory`
- `get_local_llm_status`

It must include compute tools for:

- `generate_study_plan`
- `suggest_next_task`
- `detect_duplicate_modules`
- `explain_deadline_risk`

It must include auto-tier act tools for reversible local writes:

- `add_assignment`
- `set_assignment_status`
- `set_assignment_hours`
- `add_note`
- `write_memory`
- `add_class_session`
- `add_work_shift`

It must include confirm-first act or web tools for destructive or egress work:

- `delete_modules`
- `deduplicate_modules`
- `archive_note`
- `update_memory`
- `web_search` when enabled

Any agent tool that changes state must resolve natural-language references to
stable IDs, validate arguments, pass the policy engine, and audit the result.

### Slash Command Parity

Slash commands remain deterministic shortcuts. Where a slash command and an
agent tool share behavior, they must call the same core service path or a thin
shared adapter. Telegram formatting can remain command-specific, but business
logic, validation, policy, and audit must not be duplicated.

Acceptance criteria:

- Each supported slash command has either an equivalent agent tool or an
  explicit note explaining why it stays command-only for v1.
- Agent tools and slash commands produce equivalent state changes for the same
  input.
- Confirm-first behavior is consistent between `/archive_note`, duplicate
  module deletion, web search, and future destructive tools.

## Problem 2: Planning Acceptance Gap

The planner already computes deterministic windows and assigns intensity, but
the falsifiable acceptance criteria in FR-06 need complete automated coverage.

Required tests:

- No planned block overlaps a class session or work shift.
- Daily planned minutes never exceed computed daily availability.
- A high-fatigue late shift prevents deep work before 10:00 the next morning.
- A high-fatigue work day produces only recovery or light study blocks.
- A deadline within 72 hours and high priority gets at least one block before
  the deadline, or a clear unscheduled warning.
- Planning remains deterministic for seeded fixture weeks.
- A heavy week with at least four shifts reduces total planned study minutes by
  at least 30 percent versus an otherwise-identical light week.

Implementation may satisfy this by reducing availability, capping intensity, or
both, but the behavior must be deterministic and explained in planner output.

## Problem 3: Data Model Source-Of-Truth Gap

`docs/DATA_MODEL.md` says Markdown/YAML in `memory/` is canonical and SQLite is
a derived cache. The current implementation writes operational records directly
to SQLite.

The project must choose one v1 contract:

1. Keep SQLite as the v1 source of truth for academic, knowledge, memory, trace,
   and retrieval metadata, and update docs accordingly.
2. Implement the YAML/Markdown coherence protocol, including atomic file writes,
   startup reconciliation, and `reindex(scope)`.

Recommended v1 decision: make SQLite the source of truth for v1 and document
YAML/Markdown source-of-truth as a post-v1 option. This matches the current
code, test suite, dashboard, TUI, and retrieval design.

Acceptance criteria:

- `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md`, and `docs/REQUIREMENTS.md`
  describe the same storage contract.
- No doc says SQLite is merely derived unless the reconciliation implementation
  exists.
- Backup/export work is explicitly scoped if human-readable files remain a
  product goal.

## Problem 4: Documentation And Milestone Drift

Some docs still describe already-shipped work as future priorities or current
fix targets. The docs must distinguish:

- shipped behavior
- v1 remaining work
- post-v1 deferred work
- legacy compatibility surfaces

Required updates:

- Refresh `docs/ARCHITECTURE.md` implementation priorities.
- Refresh `docs/SECURITY.md` current fix targets after verifying tests.
- Mark `NLRouter` and `NLClassifier` as compatibility-only in user-facing docs.
- Convert completed plan documents to historical records or add completion
  notes so unchecked boxes are not mistaken for current truth.

Acceptance criteria:

- A new contributor can read `docs/README.md` and know which documents are
  canonical today.
- No canonical doc says "not yet built" for behavior that tests prove is built.
- Remaining work is tracked in one current spec or plan, not scattered across
  stale checklist files.

## Problem 5: Editable Install Failure

### Failure

`pip3 install -e .` fails during editable build requirements with:

```text
Multiple top-level packages discovered in a flat-layout:
['app', 'web', 'core', 'logs', 'data', 'inbox', 'memory', 'output', 'skills'].
```

### Root Cause

The project uses a flat layout and `pyproject.toml` did not declare package
discovery. Setuptools attempted automatic discovery and found runtime/data
directories alongside Python packages. To avoid accidentally shipping local
data, logs, inbox files, or output artifacts, setuptools refuses to build.

### Required Behavior

Editable installation must include only Python packages that are part of the
Atenas application:

- `app*`
- `core*`
- `skills*`

Editable installation must exclude runtime, generated, docs, and test
directories:

- `data*`
- `logs*`
- `memory*`
- `output*`
- `inbox*`
- `web*`
- `tests*`
- `docs*`

The `app` package must include dashboard templates and static assets as package
data so non-editable installs can render the local dashboard.

Acceptance criteria:

- `pip install -e .` succeeds from a clean checkout with the existing flat
  layout.
- The `atenas` console script is installed and `atenas --help` renders.
- Runtime directories are not included as importable Python packages.
- `pytest tests/test_packaging.py -q` passes.

## Out Of Scope

- Multi-user SaaS support.
- Public dashboard/API deployment.
- Calendar/email integration.
- Autonomous shell access.
- Moving the repository to `src/` layout in v1.

## Completion Definition

This spec is complete when:

1. Editable install works and is covered by tests.
2. The v1 remaining work is either implemented or explicitly moved to post-v1.
3. Canonical docs no longer contradict implementation state.
4. Agent tool coverage matches the v1 product success criteria.
5. The full test suite passes without requiring a live local LLM.
