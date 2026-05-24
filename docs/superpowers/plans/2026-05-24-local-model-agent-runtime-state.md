# Local Model Agent Runtime State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable runtime state for Atenas local-model agent turns, starting with SQLite-backed pending actions that survive process restarts.

**Architecture:** Keep the existing `AgentLoop` and `ToolRegistry`. Add a small `AgentRuntimeStore` in `core/nl/runtime_state.py`, persist pending confirm-first actions in SQLite, and make Telegram confirmation load from the store instead of relying only on `context.user_data`. Later tasks add model profiles, tool selection, prompt assembly, and trace replay as separate slices.

**Tech Stack:** Python 3.11, SQLite, Pydantic v2, pytest, python-telegram-bot test doubles.

---

## Development Starter Prompt

Copy this prompt into a fresh Codex session when you want to start developing:

```text
We are in /Users/nathanlucio/Desktop/study-agent-cd.

Read:
- CLAUDE.md
- docs/AGENT_LOOP.md
- docs/ARCHITECTURE.md
- docs/SECURITY.md
- docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md
- docs/superpowers/plans/2026-05-24-local-model-agent-runtime-state.md

Implement Task 1 and Task 2 only: SQLite-backed agent runtime state and durable pending action storage. Use TDD. Do not change the policy model, do not add a framework dependency, and do not make dashboard/API writable.

Required behavior:
- Confirm-first actions created by AgentLoop/ToolRegistry are persisted before the Telegram user sees the confirmation prompt.
- A later Telegram context with empty user_data can still confirm or cancel the pending action for the same actor.
- A different Telegram actor cannot confirm it.
- Existing tests keep passing.

Run:
- .venv/bin/pytest tests/test_nl_commands.py tests/test_nl_agent_loop.py tests/test_db.py -q
- .venv/bin/pytest -q

Report changed files, test results, and any remaining gaps.
```

## Phase Breakdown

1. **Durable pending actions:** SQLite schema, runtime store, Telegram
   confirmation integration, `/pending`, `/cancel_pending`.
2. **Model profiles:** model capability metadata and conservative defaults for
   Ollama.
3. **Tool selection:** deterministic reduction of visible tools before each
   prompt.
4. **Prompt assembly:** model-profile budgets for history, observations, and
   selected tools.
5. **Trace replay:** CLI debugging helpers for local-model regressions.

Implement each phase as an independently testable slice.

### Task 1: Runtime State Schema And Store

**Files:**
- Modify: `core/db.py`
- Create: `core/nl/runtime_state.py`
- Test: `tests/test_agent_runtime_state.py`

- [ ] **Step 1: Write schema tests**

Create `tests/test_agent_runtime_state.py` with tests that initialize a temp DB
and assert `agent_threads` and `pending_actions` exist after `init_db(tmp_db)`.

Also test that a pending action round-trips through the future
`AgentRuntimeStore` API:

```python
from core.db import get_connection, init_db
from core.nl.runtime_state import AgentRuntimeStore
from core.nl.tool_contracts import PendingToolAction
from core.schemas import ActionCriticality, ActionOrigin, ActionProposal, ActionTier


def test_runtime_tables_exist(tmp_db):
    init_db(tmp_db)
    with get_connection(tmp_db) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "agent_threads" in tables
    assert "pending_actions" in tables


def test_pending_action_round_trips(tmp_db):
    store = AgentRuntimeStore(tmp_db)
    pending = PendingToolAction(
        tool_name="delete_modules",
        confirmation_message='Delete module? Reply "yes" to confirm or "no" to cancel.',
        proposal=ActionProposal(
            action_type="delete_modules",
            payload={"module_ids": ["m1"], "actor_user_id": 123},
            confidence=1.0,
            origin=ActionOrigin.TELEGRAM_NL,
            criticality=ActionCriticality.DESTRUCTIVE,
            action_tier=ActionTier.CONFIRM_FIRST,
        ),
    )

    record = store.save_pending_action(
        actor_user_id=123,
        channel="telegram",
        pending=pending,
    )

    loaded = store.get_active_pending_action(actor_user_id=123, channel="telegram")
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.pending.tool_name == "delete_modules"
    assert loaded.pending.proposal.action_type == "delete_modules"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_agent_runtime_state.py -q
```

Expected: import or missing-table failure.

- [ ] **Step 3: Add SQLite tables**

In `core/db.py`, append the `agent_threads` and `pending_actions` schema from
the spec to `SCHEMA_SQL`, including indexes.

- [ ] **Step 4: Implement runtime models and store**

Create `core/nl/runtime_state.py` with:

- `PendingActionRecord`
- `AgentThreadRecord`
- `AgentRuntimeStore`

Required public methods:

```python
class AgentRuntimeStore:
    def __init__(self, db_path: Path | str) -> None: ...

    def get_or_create_thread(
        self,
        *,
        actor_user_id: int,
        channel: str = "telegram",
    ) -> AgentThreadRecord: ...

    def save_conversation(
        self,
        *,
        actor_user_id: int,
        channel: str,
        conversation: list[dict[str, str]],
    ) -> AgentThreadRecord: ...

    def save_pending_action(
        self,
        *,
        actor_user_id: int,
        channel: str,
        pending: PendingToolAction,
    ) -> PendingActionRecord: ...

    def get_active_pending_action(
        self,
        *,
        actor_user_id: int,
        channel: str = "telegram",
    ) -> PendingActionRecord | None: ...

    def mark_pending_action(
        self,
        pending_id: str,
        *,
        status: str,
    ) -> None: ...
```

Use `model_dump_json()` and `model_validate_json()` for Pydantic payloads.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_agent_runtime_state.py -q
```

Expected: all tests in the file pass.

### Task 2: Telegram Durable Pending Actions

**Files:**
- Modify: `app/bot.py`
- Test: `tests/test_nl_commands.py`

- [ ] **Step 1: Add failing Telegram restart-survival tests**

In `tests/test_nl_commands.py`, add tests that:

- create duplicate modules
- send plain text that creates a confirm-first pending action
- discard `context.user_data`
- send `yes` from the same actor with a fresh context
- assert the action executes

Add a second test where actor `999` tries to confirm actor `123`'s pending
action and assert no mutation occurs.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_nl_commands.py -q
```

Expected: the new restart-survival tests fail because pending actions only live
in `context.user_data`.

- [ ] **Step 3: Wire `AgentRuntimeStore` into `natural_language_handler`**

In `app/bot.py`:

- import `AgentRuntimeStore`
- build a store from settings DB path inside `natural_language_handler`
- load active pending action from SQLite before checking `context.user_data`
- when `AgentLoop` returns `pending_action`, persist it with
  `store.save_pending_action(...)`
- on `yes`, execute the loaded pending action, then mark it `executed`
- on `no`, mark it `cancelled`
- keep `context.user_data["nl_pending_action"]` as a cache only
- persist `result.conversation` with `store.save_conversation(...)`

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_nl_commands.py tests/test_agent_runtime_state.py -q
```

Expected: all selected tests pass.

### Task 3: Pending Review Commands

**Files:**
- Modify: `app/bot.py`
- Modify: `core/command_catalog.py`
- Test: `tests/test_nl_commands.py`

- [ ] **Step 1: Add failing command tests**

Add tests for:

- `/pending` with no pending action
- `/pending` with an active pending action
- `/cancel_pending` cancels and prevents later `yes` execution

- [ ] **Step 2: Implement commands**

Add handlers:

- `pending_command`
- `cancel_pending_command`

Register them in `build_application()` and add to `COMMAND_GROUPS`.

Expected Telegram output should include action type, tool name, and
confirmation message, but not full `proposal.payload`.

- [ ] **Step 3: Run command tests**

Run:

```bash
.venv/bin/pytest tests/test_nl_commands.py tests/test_bot.py -q
```

Expected: all selected tests pass.

### Task 4: Model Profiles

**Files:**
- Create: `core/nl/model_profiles.py`
- Test: `tests/test_model_profiles.py`

- [ ] **Step 1: Add tests**

Test:

- default Ollama profile is conservative
- custom model names match by prefix or exact name
- unknown models fall back to default

- [ ] **Step 2: Implement profiles**

Create a small dataclass or Pydantic model:

```python
class ModelProfile(StrictModel):
    provider: str = "ollama"
    model: str
    context_window_tokens: int = 8192
    max_tools_per_prompt: int = 10
    max_history_items: int = 8
    max_observation_chars: int = 5000
    strict_json: bool = False
    temperature: float = 0.0
```

Add `profile_for_model(model: str) -> ModelProfile`.

- [ ] **Step 3: Run tests**

Run:

```bash
.venv/bin/pytest tests/test_model_profiles.py -q
```

Expected: all tests pass.

### Task 5: Deterministic Tool Selection

**Files:**
- Create: `core/nl/tool_selector.py`
- Modify: `core/nl/agent.py`
- Test: `tests/test_tool_selector.py`
- Test: `tests/test_nl_agent_loop.py`

- [ ] **Step 1: Add selection tests**

Test seeded messages:

- "what should I study today" selects schedule/planning tools
- "what do my notes say about transformers" selects retrieval/search tools
- "delete duplicate modules" selects duplicate detection and confirm-first
  duplicate tools
- generic greeting selects safe default read tools

- [ ] **Step 2: Implement selector**

Implement:

```python
def select_tools(
    *,
    user_message: str,
    all_tools: list[ToolDefinition],
    max_tools: int,
) -> list[ToolDefinition]:
    ...
```

Keep rule order deterministic and preserve stable sorted tool names for ties.

- [ ] **Step 3: Use selected tools in `AgentLoop`**

Add an optional selected-tools path without removing existing behavior. If no
selector/profile is supplied, keep current `schemas_for_llm()` behavior.

- [ ] **Step 4: Run focused agent tests**

Run:

```bash
.venv/bin/pytest tests/test_tool_selector.py tests/test_nl_agent_loop.py -q
```

Expected: all selected tests pass.

### Task 6: Prompt Assembler

**Files:**
- Create: `core/nl/prompt_assembler.py`
- Modify: `core/nl/agent.py`
- Test: `tests/test_prompt_assembler.py`

- [ ] **Step 1: Add budget tests**

Test that:

- history is capped by profile
- observations are capped by character budget
- omitted tool count is reported
- user text stays wrapped in `<user_input>`

- [ ] **Step 2: Extract prompt construction**

Move prompt-building logic out of `AgentLoop._build_prompt()` into
`PromptAssembler`.

Do not change the prompt rules from `AGENT_PROMPT`; only move assembly and add
budgets.

- [ ] **Step 3: Run prompt and agent tests**

Run:

```bash
.venv/bin/pytest tests/test_prompt_assembler.py tests/test_nl_agent_loop.py -q
```

Expected: all selected tests pass.

### Task 7: Trace Replay CLI

**Files:**
- Modify: `core/nl/traces.py`
- Modify: `app/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Test that `atenas traces --limit 1` still works and that a new
`atenas replay-trace TRACE_ID` prints trace steps for a known trace.

- [ ] **Step 2: Add trace detail loader**

Add `AgentTraceStore.get_trace(trace_id)` and
`AgentTraceStore.list_steps(trace_id)`.

- [ ] **Step 3: Add CLI command**

Add:

```python
@main.command("replay-trace")
@click.argument("trace_id")
def replay_trace(trace_id: str) -> None:
    ...
```

For v1, replay means "print deterministic trace detail"; do not re-run writes.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
.venv/bin/pytest tests/test_cli.py -q
```

Expected: all selected tests pass.

## Final Verification

Run:

```bash
.venv/bin/pytest -q
pip3 install -e . --no-deps --dry-run
```

If pip cannot fetch build dependencies because network is blocked, rerun the
dry-run with approved network access and report both results.

## Handoff Notes

Recommended first slice: Task 1 and Task 2 only. Do not start model profiles or
tool selection until durable pending actions are tested, because restart-safe
confirmation is the highest-value reliability improvement.
