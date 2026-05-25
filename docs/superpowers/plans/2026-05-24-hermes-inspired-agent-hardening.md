# Hermes-Inspired Agent Hardening Implementation Plan

## Historical Plan Status

This is an archival implementation plan. Its unchecked boxes preserve the
original task breakdown and are not the current project status; use
`docs/README.md` and the current gap spec for live work tracking.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the safe, useful Hermes Agent patterns into Atenas: toolsets, approved skill memory, backup/restore, local model profile config, searchable sessions, and a future channel boundary.

**Architecture:** Keep `AgentLoop`, `ToolRegistry`, and the Atenas policy model. Add internal modules that group existing tools, store approved procedural skills, back up the SQLite source of truth, make local model limits explicit, and search trace metadata. Do not add a Hermes dependency or a broad autonomous tool gateway.

**Tech Stack:** Python 3.11, SQLite, Pydantic v2, Click, pytest.

---

## Development Starter Prompt

Use this prompt after the durable pending-action work from
`docs/superpowers/plans/2026-05-24-local-model-agent-runtime-state.md` has
landed.

```text
We are in /Users/nathanlucio/Desktop/study-agent-cd.

Read:
- CLAUDE.md
- docs/AGENT_LOOP.md
- docs/ARCHITECTURE.md
- docs/SECURITY.md
- docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md
- docs/superpowers/plans/2026-05-24-hermes-inspired-agent-hardening.md

Implement Task 1 only: Hermes-inspired toolsets for Atenas.

Constraints:
- Keep AgentLoop and ToolRegistry.
- Do not add a Hermes dependency.
- Do not add terminal, browser, shell, file-editing, multi-agent, or remote gateway tools.
- TUI/dashboard toolsets must be read-only.
- Egress and destructive toolsets must never be enabled silently.
- Use TDD.

Run:
- .venv/bin/pytest tests/test_toolsets.py tests/test_nl_agent_loop.py -q
- .venv/bin/pytest -q

Report changed files, test results, and the next recommended task.
```

## Phase Breakdown

1. **Toolsets:** group existing tools by surface/risk and filter LLM-visible
   tools deterministically.
2. **Backup/restore:** protect SQLite and local state before more runtime
   memory is added.
3. **Local model profile config:** make context length, timeouts, and prompt
   limits explicit.
4. **Approved skill memory:** safe, reviewed procedural memories.
5. **Session search:** search traces and replay metadata without rerunning
   writes.
6. **Channel adapter boundary:** extract only when a second channel is scoped.

### Task 1: Toolsets

**Files:**
- Create: `core/nl/toolsets.py`
- Modify: `core/nl/tools.py`
- Modify: `core/nl/agent.py`
- Test: `tests/test_toolsets.py`
- Test: `tests/test_nl_agent_loop.py`

- [ ] **Step 1: Add failing toolset tests**

Create `tests/test_toolsets.py` with tests for:

- every registered tool belongs to at least one toolset
- `tui-readonly` and `dashboard-readonly` contain no act or web tools
- `telegram-safe` excludes `web_search`
- `telegram-egress` includes `web_search` only when web tools are enabled
- `telegram-destructive` includes confirm-first destructive tools

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_toolsets.py -q
```

Expected: import failure because `core.nl.toolsets` does not exist.

- [ ] **Step 3: Implement `core/nl/toolsets.py`**

Define:

```python
from enum import StrEnum

class ToolsetName(StrEnum):
    TELEGRAM_SAFE = "telegram-safe"
    TELEGRAM_EGRESS = "telegram-egress"
    TELEGRAM_DESTRUCTIVE = "telegram-destructive"
    TUI_READONLY = "tui-readonly"
    DASHBOARD_READONLY = "dashboard-readonly"
    DEV_LOCAL = "dev-local"
```

Add mappings from toolset names to tool names. Keep mappings explicit; do not
infer destructive behavior from substrings.

- [ ] **Step 4: Add filtering helper**

Implement:

```python
def tool_names_for_toolsets(
    toolsets: set[ToolsetName],
    *,
    web_enabled: bool,
) -> set[str]:
    ...
```

Rules:

- remove `web_search` unless `web_enabled` is true and
  `ToolsetName.TELEGRAM_EGRESS` is selected
- never include act/web tools in readonly toolsets
- return deterministic sets for tests

- [ ] **Step 5: Wire optional filtering into `ToolRegistry` or `AgentLoop`**

Prefer a small optional method on `ToolRegistry`:

```python
def list_tools_for_toolsets(self, toolsets: set[ToolsetName]) -> list[ToolDefinition]:
    ...
```

Keep `list_tools()` unchanged for backwards compatibility.

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_toolsets.py tests/test_nl_agent_loop.py -q
```

Expected: selected tests pass.

### Task 2: Backup And Restore

**Files:**
- Create: `core/backup.py`
- Modify: `app/cli.py`
- Test: `tests/test_backup.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing backup tests**

Test:

- backup creates a timestamped archive under a temp output dir
- manifest includes DB path, created time, included files, hashes, and excluded
  secret paths
- `.env` is excluded by default
- restore refuses to overwrite an existing DB without `force=True`

- [ ] **Step 2: Implement backup service**

Create `BackupService` with:

```python
class BackupService:
    def create_backup(self, *, include_logs: bool = False) -> Path: ...
    def restore_backup(self, archive_path: Path, *, force: bool = False) -> None: ...
```

Use `zipfile` from the standard library. Keep file selection explicit.

- [ ] **Step 3: Add CLI commands**

Add:

```python
@main.command()
@click.option("--include-logs", is_flag=True)
def backup(include_logs: bool) -> None: ...

@main.command()
@click.argument("archive_path")
@click.option("--force", is_flag=True)
def restore(archive_path: str, force: bool) -> None: ...
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_backup.py tests/test_cli.py -q
```

Expected: selected tests pass.

### Task 3: Local Model Profile Config

**Files:**
- Modify: `app/config.py`
- Modify: `app/cli.py`
- Create: `core/nl/model_profiles.py`
- Test: `tests/test_config.py`
- Test: `tests/test_model_profiles.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add settings tests**

Test defaults and env overrides for:

- `OLLAMA_CONTEXT_LENGTH`
- `OLLAMA_STREAM_TIMEOUT_SECONDS`
- `AGENT_MAX_PROMPT_CHARS`
- `AGENT_MAX_TOOLS_PER_PROMPT`
- `AGENT_MODEL_PROFILE`

- [ ] **Step 2: Implement `ModelProfile`**

Create:

```python
class ModelProfile(StrictModel):
    provider: str = "ollama"
    model: str
    context_window_tokens: int
    stream_timeout_seconds: int
    max_prompt_chars: int
    max_tools_per_prompt: int
    strict_json: bool = False
```

Add `profile_from_settings(settings) -> ModelProfile`.

- [ ] **Step 3: Extend doctor output**

Show model, base URL, context length, stream timeout, and prompt/tool limits.
Warn if context length is below `8192`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_config.py tests/test_model_profiles.py tests/test_cli.py -q
```

Expected: selected tests pass.

### Task 4: Approved Skill Memory

**Files:**
- Modify: `core/db.py`
- Create: `core/agent_skills.py`
- Modify: `core/nl/tools.py`
- Test: `tests/test_agent_skills.py`

- [ ] **Step 1: Add failing skill repository tests**

Test proposing, approving, listing active, retrieving by tag/kind, and
archiving a skill.

- [ ] **Step 2: Add schema**

Add `agent_skills` table from the Hermes-inspired spec.

- [ ] **Step 3: Implement service**

Create `AgentSkillService` with:

- `propose_skill`
- `approve_skill`
- `archive_skill`
- `list_active`
- `search`

- [ ] **Step 4: Add read-only agent tool**

Add `search_agent_skills` as a read tool. Do not add autonomous skill creation
to the LLM path in this task.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_agent_skills.py tests/test_nl_agent_loop.py -q
```

Expected: selected tests pass.

### Task 5: Session Search And Replay

**Files:**
- Modify: `core/nl/traces.py`
- Modify: `app/cli.py`
- Modify: `core/nl/tools.py`
- Test: `tests/test_agent_traces.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_nl_agent_loop.py`

- [ ] **Step 1: Add trace search tests**

Test search by:

- user message summary
- final message summary
- tool name
- trace status

- [ ] **Step 2: Add trace store search methods**

Add:

```python
def search(self, query: str, *, limit: int = 20) -> list[dict[str, object]]: ...
def get_trace(self, trace_id: str) -> dict[str, object] | None: ...
def list_steps(self, trace_id: str) -> list[dict[str, object]]: ...
```

- [ ] **Step 3: Add CLI replay command**

Add `atenas replay-trace TRACE_ID`. It prints metadata and steps only. It must
never rerun writes.

- [ ] **Step 4: Add read-only agent tool**

Add `search_agent_history` as a read tool over trace summaries.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_agent_traces.py tests/test_cli.py tests/test_nl_agent_loop.py -q
```

Expected: selected tests pass.

### Task 6: Channel Adapter Boundary

**Files:**
- Create: `core/messages.py`
- Modify: `app/bot.py`
- Test: `tests/test_messages.py`
- Test: `tests/test_nl_commands.py`

- [ ] **Step 1: Add message model tests**

Test:

- `Actor`
- `Channel`
- `InboundMessage`
- `OutboundMessage`
- `ConfirmationIntent`

- [ ] **Step 2: Implement models**

Keep models small Pydantic objects. Telegram actor ID remains authoritative.

- [ ] **Step 3: Use models in Telegram NL handler**

Wrap Telegram inputs into `InboundMessage` before passing actor/channel data to
runtime state and agent code.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_messages.py tests/test_nl_commands.py -q
```

Expected: selected tests pass.

## Final Verification

After any phase, run:

```bash
.venv/bin/pytest -q
pip3 install -e . --no-deps --dry-run
```

If pip cannot fetch build dependencies because network is blocked, rerun the
dry-run with approved network access and report both results.

## Recommended First Slice

Start with Task 1, toolsets. It is the lowest-risk Hermes-inspired change and
it immediately helps local models by reducing the tool catalog they see.

Then do Task 2, backup/restore, before adding more persistent runtime or skill
state.
