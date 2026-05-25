# Atenas Audit Hardening Implementation Plan

## Historical Plan Status

This is an archival implementation plan. Its unchecked boxes preserve the
original task breakdown and are not the current project status; use
`docs/README.md` and the current gap spec for live work tracking.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Atenas' security, action governance, local-only posture, planning contract, and verification pipeline back into alignment with the product/security specs.

**Architecture:** Fix safety at shared boundaries first: file access policy, action-tier gate, policy engine, local transport guard, and LLM/egress configuration. Then align product behavior and tests: planning acceptance criteria, legacy NL quarantine, and one canonical retrieval schema owner. Keep changes small and service-centered so Telegram, API, dashboard, and LLM tools cannot drift into separate safety models again.

**Tech Stack:** Python 3.11, FastAPI, python-telegram-bot, Pydantic v2, SQLite, pytest, pytest-asyncio.

---

## Scope And Ordering

This plan is intentionally split into three cycles.

1. **Cycle 1: Safety and governance.** Must ship first. It closes the real security and mutation bypasses.
2. **Cycle 2: Product/spec alignment.** Makes planning and logging match the documented v1 contract or updates docs where v1 intentionally stays smaller.
3. **Cycle 3: Architecture cleanup.** Reduces future regression risk by removing duplicate NL architecture and splitting oversized adapter code.

Do not start Cycle 2 until Cycle 1 has tests passing. Do not start Cycle 3 until the behavioral contract is stable.

## File Structure

Create:

- `core/path_policy.py` — canonical file/path allowlist and secret/source-path rejection.
- `tests/test_path_policy.py` — unit tests for path policy.
- `tests/test_local_transport.py` — loopback-only settings and request guard tests.
- `docs/DECISIONS.md` — short architecture decision log for local-only and egress rules.

Modify:

- `app/config.py` — add knowledge roots, loopback/default-local settings, external Ollama opt-in, pytest import slowness investigation notes if needed.
- `app/main.py` — add non-loopback dashboard/API request guard.
- `app/bot.py` — route `/archive_note` through the pending action flow; tighten plain-message auth helper; later split in Cycle 3.
- `Dockerfile` and `docker-compose.yml` — make bind-host behavior explicit.
- `core/knowledge/service.py` — enforce file registration root policy.
- `core/retrieval/service.py` — read only policy-approved registered files.
- `core/nl/tools.py` — route memory writes and web search through `_gate_action`; move web network call to confirmed execution.
- `core/nl/tool_contracts.py` — keep schemas aligned with memory/web governance.
- `core/policy_engine.py` — add memory and egress actions to the correct allow/confirm sets.
- `core/action_executor.py` — reuse audit summaries for new action handlers; add redaction keys if needed.
- `core/db.py` and `core/retrieval/vector_store.py` — make `retrieval_chunks` schema single-owned.
- `core/academic/availability.py`, `core/academic/planner.py`, `core/academic/models.py` — implement planning fatigue/intensity only if Cycle 2 chooses implementation over spec downgrade.
- `docs/REQUIREMENTS.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/AGENT_LOOP.md` — reconcile shipped behavior with target contract.
- Relevant tests under `tests/`, `tests/retrieval/`, and `tests/academic/`.

---

## Cycle 1: Safety And Governance

### Task 1: Add A Canonical File Path Policy

**Files:**
- Create: `core/path_policy.py`
- Create: `tests/test_path_policy.py`
- Modify: `core/knowledge/service.py`
- Modify: `core/retrieval/service.py`
- Modify: `app/config.py`
- Modify: `app/bot.py`
- Modify: `app/dashboard.py`
- Modify: `tests/retrieval/test_retrieval_service.py`

- [ ] **Step 1: Write failing policy tests**

Add `tests/test_path_policy.py`:

```python
from pathlib import Path

import pytest

from core.path_policy import PathPolicy, PathPolicyError


def test_allows_file_inside_allowed_root(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    allowed = inbox / "reading.txt"
    allowed.write_text("safe text", encoding="utf-8")

    policy = PathPolicy([inbox])

    assert policy.validate_registered_file(allowed) == allowed.resolve()


def test_rejects_env_file_even_inside_allowed_root(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    env_file = inbox / ".env"
    env_file.write_text("TOKEN=secret", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="hidden or secret"):
        policy.validate_registered_file(env_file)


def test_rejects_parent_directory_escape(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not allowed", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="allowed roots"):
        policy.validate_registered_file(inbox / ".." / "outside.txt")


def test_rejects_symlink_escape(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not allowed", encoding="utf-8")
    link = inbox / "linked.txt"
    link.symlink_to(outside)

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="allowed roots"):
        policy.validate_registered_file(link)


def test_rejects_source_files_by_suffix(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "app.py"
    source.write_text("print('no')", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="source code"):
        policy.validate_registered_file(source)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/test_path_policy.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'core.path_policy'`.

- [ ] **Step 3: Implement `core/path_policy.py`**

Create `core/path_policy.py`:

```python
"""Filesystem access policy for user-registered Atenas files."""

from __future__ import annotations

from pathlib import Path

SECRET_NAMES = {".env", ".env.local", ".netrc", "id_rsa", "id_ed25519"}
SECRET_PARTS = {".ssh", ".gnupg", ".aws", ".config"}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".sh", ".zsh"}


class PathPolicyError(ValueError):
    """Raised when a path violates Atenas file access policy."""


class PathPolicy:
    """Allow registered files only inside configured, non-secret data roots."""

    def __init__(self, allowed_roots: list[Path | str]) -> None:
        roots = [Path(root).expanduser().resolve() for root in allowed_roots]
        self.allowed_roots = [root for root in roots if root.exists()]
        if not self.allowed_roots:
            raise PathPolicyError("At least one existing allowed file root is required.")

    def validate_registered_file(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise PathPolicyError("File not found.") from exc

        if not resolved.is_file():
            raise PathPolicyError("Registered path must be a file.")
        if not self._inside_allowed_root(resolved):
            raise PathPolicyError("File must be inside one of the configured allowed roots.")
        if self._is_hidden_or_secret(resolved):
            raise PathPolicyError("Refusing hidden or secret file path.")
        if resolved.suffix.lower() in SOURCE_SUFFIXES:
            raise PathPolicyError("Refusing source code file path.")
        return resolved

    def _inside_allowed_root(self, path: Path) -> bool:
        return any(path == root or root in path.parents for root in self.allowed_roots)

    def _is_hidden_or_secret(self, path: Path) -> bool:
        parts = set(path.parts)
        if path.name in SECRET_NAMES:
            return True
        if parts & SECRET_PARTS:
            return True
        return any(part.startswith(".") for part in path.relative_to(self._matching_root(path)).parts)

    def _matching_root(self, path: Path) -> Path:
        for root in self.allowed_roots:
            if path == root or root in path.parents:
                return root
        return self.allowed_roots[0]
```

- [ ] **Step 4: Wire roots through settings**

In `app/config.py`, add the setting near directory settings:

```python
    knowledge_file_roots: list[Path] = Field(default_factory=lambda: [Path("inbox"), Path("memory")])
```

Add this validator below `parse_allowed_user_ids`:

```python
    @field_validator("knowledge_file_roots", mode="before")
    @classmethod
    def parse_knowledge_file_roots(cls, value: object) -> object:
        if value is None or value == "":
            return [Path("inbox"), Path("memory")]
        if isinstance(value, str):
            return [Path(item.strip()) for item in value.split(",") if item.strip()]
        return value
```

- [ ] **Step 5: Enforce policy in `KnowledgeService`**

Change `KnowledgeService.__init__` signature in `core/knowledge/service.py`:

```python
from core.path_policy import PathPolicy, PathPolicyError


class KnowledgeService:
    def __init__(
        self,
        db_path: Path | str,
        timezone: str | ZoneInfo = "Europe/Dublin",
        allowed_file_roots: list[Path | str] | None = None,
    ) -> None:
        self.timezone = timezone if isinstance(timezone, ZoneInfo) else ZoneInfo(timezone)
        self.repository = KnowledgeRepository(db_path)
        self.search_engine = SearchEngine(db_path)
        self._academic_repo = AcademicRepository(db_path, self.timezone)
        self._path_policy = PathPolicy(allowed_file_roots or [Path("inbox"), Path("memory")])
```

In `register_file`, replace the current `Path(path)` existence handling with:

```python
        try:
            resolved_path = self._path_policy.validate_registered_file(path)
        except PathPolicyError as exc:
            return CommandResult(success=False, message=str(exc))

        path = str(resolved_path)
        file_path = resolved_path
```

Keep duplicate detection and metadata based on the resolved path.

- [ ] **Step 6: Pass settings roots from app surfaces**

In `app/bot.py`, update `KnowledgeService(...)` construction sites to pass:

```python
allowed_file_roots=settings.knowledge_file_roots
```

In `app/dashboard.py`, update `_get_knowledge_service`:

```python
def _get_knowledge_service(settings: Settings) -> KnowledgeService:
    return KnowledgeService(
        settings.db_path,
        timezone=settings.timezone,
        allowed_file_roots=settings.knowledge_file_roots,
    )
```

In `core/nl/tools.py`, add `allowed_file_roots` to `ToolRegistry.__init__` and pass it into `KnowledgeService`.

- [ ] **Step 7: Ensure retrieval refuses unapproved legacy paths**

In `core/retrieval/service.py`, accept `allowed_file_roots` in `__init__`, construct `PathPolicy`, and change `_read_registered_text_file`:

```python
        try:
            path = self._path_policy.validate_registered_file(file_record.path)
        except PathPolicyError:
            return None
```

Then keep the existing text-file and read logic.

- [ ] **Step 8: Update retrieval tests to register files under an allowed root**

Where tests create a `RetrievalService`, pass the temp directory as root:

```python
return RetrievalService(db_path, ollama_model="test-model", allowed_file_roots=[tmp_path])
```

- [ ] **Step 9: Run focused path and retrieval tests**

Run:

```bash
.venv/bin/pytest tests/test_path_policy.py tests/retrieval/test_retrieval_service.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add app/config.py app/bot.py app/dashboard.py core/path_policy.py core/knowledge/service.py core/retrieval/service.py core/nl/tools.py tests/test_path_policy.py tests/retrieval/test_retrieval_service.py
git commit -m "fix: restrict registered file access"
```

### Task 2: Make Memory Tools Policy-Governed And Audited

**Files:**
- Modify: `core/policy_engine.py`
- Modify: `core/nl/tools.py`
- Modify: `core/nl/tool_contracts.py`
- Modify: `tests/test_policy_engine.py`
- Modify: `tests/test_nl_agent_loop.py`

- [ ] **Step 1: Write failing policy tests**

Add to `tests/test_policy_engine.py`:

```python
def test_update_memory_requires_confirmation() -> None:
    decision = PolicyEngine().check(proposal("update_memory"))

    assert decision.allowed is False
    assert decision.outcome == ActionOutcome.NEEDS_CONFIRMATION


def test_write_memory_is_auto_tier_allowed_when_declared_auto() -> None:
    decision = PolicyEngine().check(
        ActionProposal(
            action_type="write_memory",
            payload={},
            confidence=1.0,
            origin=ActionOrigin.TELEGRAM_NL,
            criticality=ActionCriticality.LOCAL_WRITE,
            action_tier=ActionTier.AUTO,
        )
    )

    assert decision.allowed is True
    assert decision.outcome == ActionOutcome.SUCCESS
```

Import `ActionTier` at the top of the file.

- [ ] **Step 2: Write failing agent-loop tests**

Add to `tests/test_nl_agent_loop.py`:

```python
def test_write_memory_executes_through_action_executor(tmp_db: Path, caplog) -> None:
    registry = ToolRegistry(tmp_db)
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "write_memory",
            "arguments": {
                "content": "Nathan prefers morning study blocks.",
                "summary": "Prefers morning study blocks",
                "domain": "preferences",
                "topic": "study_schedule",
                "tags": ["planning"],
                "importance": "medium",
                "inferred": False,
                "sensitive": False,
            },
        },
        {"type": "final", "message": "Memory stored."},
    ])
    agent = AgentLoop(registry=registry, client=client)
    caplog.set_level(logging.INFO, logger="core.action_executor")

    result = agent.run("remember I prefer morning study", actor_user_id=123)

    assert result.pending_action is None
    assert result.message == "Memory stored."
    audit = [record for record in caplog.records if record.message == "action_executed"][-1]
    assert audit.action_type == "write_memory"
    assert audit.actor_user_id == 123
    assert audit.policy_allowed is True


def test_update_memory_requires_confirmation(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db)
    created, _ = registry._memory().write(
        content="Old preference",
        summary="Old preference",
        domain=MemoryDomain.PREFERENCES,
        topic="study_schedule",
    )
    client = FakeToolClient([
        {
            "type": "tool_call",
            "tool_name": "update_memory",
            "arguments": {
                "memory_id": created.id,
                "summary": "Updated preference",
            },
        },
    ])
    agent = AgentLoop(registry=registry, client=client)

    result = agent.run("update that memory", actor_user_id=123)

    assert result.pending_action is not None
    assert "Update memory" in result.message
    assert registry._memory().read_by_id(created.id).summary == "Old preference"
```

Import `MemoryDomain` from `core.schemas`.

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_policy_engine.py::test_update_memory_requires_confirmation tests/test_nl_agent_loop.py::test_write_memory_executes_through_action_executor tests/test_nl_agent_loop.py::test_update_memory_requires_confirmation -q
```

Expected: FAIL because memory tools currently bypass `ActionExecutor` and `update_memory` is not policy-classified.

- [ ] **Step 4: Update policy sets**

In `core/policy_engine.py`, add `"update_memory"` to `CONFIRMATION_REQUIRED` and keep `"write_memory"` in `ALLOWED_ACTIONS`:

```python
CONFIRMATION_REQUIRED: frozenset[str] = frozenset(
    {
        "delete_file",
        "overwrite_memory",
        "update_memory",
        "clear_work_schedule",
        "remove_assignment",
        "delete_modules",
        "deduplicate_modules",
        "change_config",
        "send_external_message",
        "archive_plan",
        "archive_note",
    }
)
```

- [ ] **Step 5: Register memory action handlers**

In `ToolRegistry._register_action_handlers`, add:

```python
        self.action_executor.register_action("write_memory", self._execute_write_memory)
        self.action_executor.register_action("update_memory", self._execute_update_memory)
```

- [ ] **Step 6: Route `write_memory` through `_gate_action`**

Replace the direct mutation tail of `_tool_write_memory` with:

```python
        payload = {
            "content": parsed.content,
            "summary": parsed.summary,
            "domain": domain.value,
            "topic": parsed.topic,
            "tags": parsed.tags,
            "importance": importance.value,
            "inferred": parsed.inferred,
            "sensitive": parsed.sensitive,
        }
        return self._gate_action(
            tool_name="write_memory",
            action_type="write_memory",
            payload=payload,
            tier=ActionTier.AUTO,
            criticality=ActionCriticality.LOCAL_WRITE,
            actor_user_id=actor_user_id,
            confirmation_message="",
        )
```

Add `_execute_write_memory`:

```python
    def _execute_write_memory(self, payload: dict[str, Any]) -> ActionResult:
        created, conflicts = self._memory().write(
            content=payload["content"],
            summary=payload["summary"],
            domain=MemoryDomain(payload["domain"]),
            topic=payload["topic"],
            tags=payload.get("tags") or [],
            importance=Importance(payload["importance"]),
            inferred=bool(payload.get("inferred", True)),
            sensitive=bool(payload.get("sensitive", False)),
        )
        result_payload = {
            "record_id": created.id,
            "memory_id": created.id,
            "conflict_count": len(conflicts),
        }
        return ActionResult(
            action_type="write_memory",
            outcome=ActionOutcome.SUCCESS,
            message=f"Memory stored\n\n#{created.id[:8]} {created.summary}",
            payload=result_payload,
        )
```

Import `ActionOutcome` if it is not already imported.

- [ ] **Step 7: Route `update_memory` through confirm-first**

Replace the direct mutation tail of `_tool_update_memory` with:

```python
        payload = {
            "memory_id": parsed.memory_id,
            "content": parsed.content,
            "summary": parsed.summary,
            "topic": parsed.topic,
            "tags": parsed.tags,
            "importance": importance.value if importance else None,
            "before_state": {
                "id": existing.id,
                "summary": existing.summary,
                "domain": existing.domain.value,
                "topic": existing.topic,
                "tags": existing.tags,
                "importance": existing.importance.value,
                "inferred": existing.inferred,
                "sensitive": existing.sensitive,
            },
        }
        return self._gate_action(
            tool_name="update_memory",
            action_type="update_memory",
            payload=payload,
            tier=ActionTier.CONFIRM_FIRST,
            criticality=ActionCriticality.LOCAL_WRITE,
            actor_user_id=actor_user_id,
            confirmation_message=(
                f'Update memory #{existing.id[:8]} — "{existing.summary}"?\n\n'
                'Reply "yes" to confirm or "no" to cancel.'
            ),
        )
```

Add `_execute_update_memory`:

```python
    def _execute_update_memory(self, payload: dict[str, Any]) -> ActionResult:
        importance = payload.get("importance")
        updated = self._memory().update(
            payload["memory_id"],
            content=payload.get("content"),
            summary=payload.get("summary"),
            topic=payload.get("topic"),
            tags=payload.get("tags"),
            importance=Importance(importance) if importance else None,
        )
        if updated is None:
            return ActionResult(
                action_type="update_memory",
                outcome=ActionOutcome.ERROR,
                message="Failed to update memory item.",
            )
        return ActionResult(
            action_type="update_memory",
            outcome=ActionOutcome.SUCCESS,
            message=f"Memory updated\n\n#{updated.id[:8]} {updated.summary}",
            payload={
                "record_id": updated.id,
                "memory_id": updated.id,
                "after_state": {
                    "id": updated.id,
                    "summary": updated.summary,
                    "domain": updated.domain.value,
                    "topic": updated.topic,
                    "tags": updated.tags,
                    "importance": updated.importance.value,
                    "inferred": updated.inferred,
                    "sensitive": updated.sensitive,
                },
            },
        )
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_policy_engine.py tests/test_nl_agent_loop.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/policy_engine.py core/nl/tools.py core/nl/tool_contracts.py tests/test_policy_engine.py tests/test_nl_agent_loop.py
git commit -m "fix: govern memory tools through policy"
```

### Task 3: Route `/archive_note` Through Pending Confirmation

**Files:**
- Modify: `app/bot.py`
- Modify: `tests/test_data_commands.py` or create `tests/test_note_commands.py`

- [ ] **Step 1: Write failing command test**

Create `tests/test_note_commands.py` if note command tests are not already isolated:

```python
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.bot import archive_note_command, natural_language_handler
from core.nl.tool_contracts import PendingToolAction


@pytest.mark.asyncio
async def test_archive_note_command_creates_pending_action_not_direct_archive() -> None:
    update = _make_update(123, "/archive_note 4")
    context = _make_context()

    with patch("app.bot._build_nl_tool_registry") as build_registry:
        registry = build_registry.return_value
        registry.run_tool.return_value.pending_action = object()
        registry.run_tool.return_value.result.message = 'Archive note #4 — "Test"?'
        await archive_note_command(update, context)

    registry.run_tool.assert_called_once_with(
        "archive_note",
        {"note": "4"},
        actor_user_id=123,
    )
    assert context.user_data["nl_pending_action"] is registry.run_tool.return_value.pending_action
    assert "Archive note" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_confirming_pending_archive_uses_registry_execute_pending() -> None:
    pending = object()
    update = _make_update(123, "yes")
    context = _make_context(user_data={"nl_pending_action": pending})

    with patch("app.bot._build_nl_tool_registry") as build_registry:
        registry = build_registry.return_value
        registry.execute_pending.return_value.message = "Note archived"
        await natural_language_handler(update, context)

    registry.execute_pending.assert_called_once_with(pending, actor_user_id=123)
    assert "Note archived" in update.effective_message.reply_text.await_args.args[0]


def _make_update(user_id: int, text: str):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    user = SimpleNamespace(id=user_id)
    return SimpleNamespace(effective_message=message, effective_user=user)


def _make_context(user_data: dict | None = None):
    settings = SimpleNamespace(TELEGRAM_ALLOWED_USER_IDS=[123])
    return SimpleNamespace(bot_data={"settings": settings}, user_data=user_data or {})
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_note_commands.py -q
```

Expected: FAIL because `/archive_note` currently calls `KnowledgeService.archive_note` directly.

- [ ] **Step 3: Change `/archive_note` command handler**

Replace the direct service logic in `archive_note_command` with:

```python
async def archive_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await _reply(update, "Usage: /archive_note <id>")
        return
    note_ref = parts[1].strip()
    if not note_ref:
        await _reply(update, "Usage: /archive_note <id>")
        return

    user_id = update.effective_user.id if update.effective_user else None
    registry = _build_nl_tool_registry(context)
    run = registry.run_tool("archive_note", {"note": note_ref}, actor_user_id=user_id)
    if run.pending_action is not None:
        user_data = getattr(context, "user_data", None)
        if user_data is None:
            user_data = {}
            context.user_data = user_data
        user_data["nl_pending_action"] = run.pending_action
    await _reply(update, run.result.message)
```

- [ ] **Step 4: Make pending confirmation type-flexible**

In `natural_language_handler`, remove the `isinstance(pending, PendingToolAction)` guard or support both current and test doubles:

```python
            result = registry.execute_pending(pending, actor_user_id=user_id)
            await _reply(update, result.message)
```

Keep production tests that store actual `PendingToolAction`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_note_commands.py tests/test_nl_agent_loop.py::test_archive_note_requires_confirmation_then_executes -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bot.py tests/test_note_commands.py
git commit -m "fix: confirm archive note command"
```

### Task 4: Make Web Search Confirm-First Egress

**Files:**
- Modify: `core/policy_engine.py`
- Modify: `core/nl/tools.py`
- Modify: `tests/test_nl_agent_loop.py`

- [ ] **Step 1: Replace web tests with egress confirmation expectations**

Update `test_web_search_returns_results` in `tests/test_nl_agent_loop.py`:

```python
def test_web_search_requires_confirmation_before_network(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)

    with patch("urllib.request.urlopen") as mock_urlopen:
        run = registry.run_tool(
            "web_search",
            {"query": "Test Query"},
            actor_user_id=123,
        )

    mock_urlopen.assert_not_called()
    assert run.pending_action is not None
    assert run.result.pending is True
    assert "Web search sends this query off-device" in run.result.message
    assert "Test Query" in run.result.message
```

Add:

```python
def test_confirmed_web_search_executes_network(tmp_db: Path) -> None:
    registry = ToolRegistry(tmp_db, web_enabled=True)
    pending = registry.run_tool(
        "web_search",
        {"query": "Test Query"},
        actor_user_id=123,
    ).pending_action
    mock_response = json.dumps([
        "Test Query",
        ["Result 1"],
        ["Snippet 1"],
        ["http://example.com/1"],
    ]).encode("utf-8")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda s, *a: None
        mock_urlopen.return_value.read = lambda: mock_response

        result = registry.execute_pending(pending, actor_user_id=123)

    assert result.ok is True
    assert "web result" in result.message.lower()
    assert result.data["query"] == "Test Query"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_nl_agent_loop.py::test_web_search_requires_confirmation_before_network tests/test_nl_agent_loop.py::test_confirmed_web_search_executes_network -q
```

Expected: FAIL because `web_search` currently performs network access immediately.

- [ ] **Step 3: Classify `web_search` as confirmation-required**

In `core/policy_engine.py`, add `"web_search"` to `CONFIRMATION_REQUIRED`.

- [ ] **Step 4: Register a web action handler**

In `_register_action_handlers`:

```python
        self.action_executor.register_action("web_search", self._execute_web_search)
```

- [ ] **Step 5: Change `_tool_web_search` to build a pending action**

Replace `_tool_web_search` with:

```python
    def _tool_web_search(self, args: BaseModel, actor_user_id: int | None) -> ToolRun:
        parsed = typed(args, WebSearchArgs)
        query = parsed.query.strip()
        if len(query) < 2:
            return tool_error("Search query must be at least 2 characters.")
        return self._gate_action(
            tool_name="web_search",
            action_type="web_search",
            payload={"query": query, "destination": "https://en.wikipedia.org"},
            tier=ActionTier.CONFIRM_FIRST,
            criticality=ActionCriticality.EXTERNAL,
            actor_user_id=actor_user_id,
            confirmation_message=(
                "Web search sends this query off-device to Wikipedia:\n\n"
                f"{query}\n\n"
                'Reply "yes" to confirm or "no" to cancel.'
            ),
        )
```

- [ ] **Step 6: Move network access to `_execute_web_search`**

Add:

```python
    def _execute_web_search(self, payload: dict[str, Any]) -> ActionResult:
        import json as _json
        import urllib.parse
        import urllib.request

        query = str(payload["query"]).strip()
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded}&limit=3&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "Atenas/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return ActionResult(
                action_type="web_search",
                outcome=ActionOutcome.ERROR,
                message=f"Web search failed: {exc}",
            )

        results = []
        if len(data) >= 4 and data[0]:
            descriptions = data[2] if len(data) > 2 else ["" for _ in data[0]]
            links = data[3] if len(data) > 3 else ["" for _ in data[0]]
            for title, desc, link in zip(data[1], descriptions, links):
                results.append({"title": title, "url": link, "snippet": desc})
        wrapped = [
            {"title": r["title"], "content": wrap_web_content(r["url"], r["snippet"])}
            for r in results
        ]
        return ActionResult(
            action_type="web_search",
            outcome=ActionOutcome.SUCCESS,
            message=f"Found {len(results)} web result(s). Web content is untrusted data.",
            payload={"query": query, "results": wrapped},
        )
```

Also import `ActionOutcome` and `urllib.error`.

- [ ] **Step 7: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_nl_agent_loop.py::test_web_tool_disabled_by_default tests/test_nl_agent_loop.py::test_web_tool_enabled_when_flag_set tests/test_nl_agent_loop.py::test_web_search_requires_confirmation_before_network tests/test_nl_agent_loop.py::test_confirmed_web_search_executes_network tests/test_nl_agent_loop.py::test_web_search_short_query_rejected -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/policy_engine.py core/nl/tools.py tests/test_nl_agent_loop.py
git commit -m "fix: require confirmation for web egress"
```

### Task 5: Enforce Loopback-Only Local LLM And Local API Access

**Files:**
- Modify: `app/config.py`
- Modify: `app/main.py`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Create: `tests/test_local_transport.py`

- [ ] **Step 1: Write loopback settings tests**

Create `tests/test_local_transport.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_default_ollama_url_is_loopback() -> None:
    settings = Settings(_env_file=None)

    assert settings.ollama_base_url == "http://localhost:11434"


def test_remote_ollama_url_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="non-loopback Ollama"):
        Settings(_env_file=None, ollama_base_url="http://192.168.1.20:11434")


def test_remote_ollama_url_allowed_with_explicit_egress_opt_in() -> None:
    settings = Settings(
        _env_file=None,
        ollama_base_url="http://192.168.1.20:11434",
        allow_external_ollama=True,
    )

    assert settings.allow_external_ollama is True


def test_non_loopback_request_is_rejected_when_local_only(settings: Settings) -> None:
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/health", headers={"x-forwarded-for": "203.0.113.10"})

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_local_transport.py -q
```

Expected: FAIL because settings and middleware do not exist yet.

- [ ] **Step 3: Add config settings and validators**

In `app/config.py`, add:

```python
    allow_external_ollama: bool = False
    allow_non_loopback_clients: bool = False
```

Add imports:

```python
import ipaddress
from urllib.parse import urlparse
```

Add model validator:

```python
    @model_validator(mode="after")
    def validate_local_egress_settings(self) -> "Settings":
        parsed = urlparse(self.ollama_base_url)
        host = parsed.hostname
        if host and not self.allow_external_ollama and not _is_loopback_host(host):
            raise ValueError(
                "Refusing non-loopback Ollama URL without allow_external_ollama=true."
            )
        return self
```

Add module helper:

```python
def _is_loopback_host(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
```

- [ ] **Step 4: Add local-only request middleware**

In `app/main.py`, import:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
import ipaddress
```

Inside `create_app`, after `app = FastAPI(...)`, add:

```python
    @app.middleware("http")
    async def local_only_guard(request: Request, call_next):
        if runtime_settings.allow_non_loopback_clients:
            return await call_next(request)
        client_host = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_host and request.client is not None:
            client_host = request.client.host
        if client_host and not _is_loopback_or_test_client(client_host):
            return JSONResponse({"detail": "Atenas API/dashboard is local-only."}, status_code=403)
        return await call_next(request)
```

At module level:

```python
def _is_loopback_or_test_client(host: str) -> bool:
    if host == "testclient":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"
```

- [ ] **Step 5: Make container binding explicit**

Change `Dockerfile` command to default local-only:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
```

In `docker-compose.yml`, override command for container networking while preserving host localhost publishing:

```yaml
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Keep:

```yaml
    ports:
      - "127.0.0.1:8000:8000"
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_config.py tests/test_api.py tests/test_local_transport.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/main.py Dockerfile docker-compose.yml tests/test_local_transport.py
git commit -m "fix: enforce local-only runtime defaults"
```

### Task 6: Tighten Telegram Plain-Message Authorization

**Files:**
- Modify: `app/bot.py`
- Modify: `tests/test_bot.py`

- [ ] **Step 1: Add failing tests**

Add to `tests/test_bot.py`:

```python
def test_plain_message_auth_default_denies_empty_allowlist() -> None:
    settings = SimpleNamespace(TELEGRAM_ALLOWED_USER_IDS=[])

    assert _telegram_user_authorized(settings, 123) is False


def test_plain_message_auth_default_denies_malformed_allowlist() -> None:
    settings = SimpleNamespace(TELEGRAM_ALLOWED_USER_IDS="123")

    assert _telegram_user_authorized(settings, 123) is False
```

Import `_telegram_user_authorized` from `app.bot` if it is not already imported.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_bot.py::test_plain_message_auth_default_denies_empty_allowlist tests/test_bot.py::test_plain_message_auth_default_denies_malformed_allowlist -q
```

Expected: FAIL because helper currently returns `True`.

- [ ] **Step 3: Change helper to default-deny**

Replace `_telegram_user_authorized` with:

```python
def _telegram_user_authorized(settings: Settings, user_id: int | None) -> bool:
    """Return whether a plain-message handler should process this user."""

    allowed_user_ids = getattr(settings, "TELEGRAM_ALLOWED_USER_IDS", [])
    if not isinstance(allowed_user_ids, Sequence) or isinstance(allowed_user_ids, (str, bytes)):
        return False
    if not allowed_user_ids:
        return False
    return user_id is not None and user_id in set(allowed_user_ids)
```

- [ ] **Step 4: Run focused bot tests**

Run:

```bash
.venv/bin/pytest tests/test_bot.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bot.py tests/test_bot.py
git commit -m "fix: default-deny telegram plain auth"
```

---

## Cycle 2: Product And Spec Alignment

### Task 7: Decide And Implement Planning Contract

**Files:**
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/PRODUCT_SPEC.md`
- Modify: `core/academic/models.py`
- Modify: `core/academic/availability.py`
- Modify: `core/academic/planner.py`
- Modify: `tests/academic/test_availability.py`
- Modify: `tests/academic/test_planner.py`

- [ ] **Step 1: Choose implementation over downgrade**

Record this decision in `docs/DECISIONS.md`:

```markdown
## 2026-05-21 — Planning Contract

Atenas keeps the v1 requirement that work fatigue affects planning intensity.
The planner remains deterministic: code computes study windows and their
maximum intensity, then assigns work without LLM-authored times.
```

- [ ] **Step 2: Add failing availability fatigue tests**

Add to `tests/academic/test_availability.py`:

```python
def test_high_fatigue_shift_reduces_next_morning_window_to_light() -> None:
    shift = _work_shift(
        start_at=datetime(2026, 5, 18, 18, 0, tzinfo=TZ),
        end_at=datetime(2026, 5, 18, 23, 30, tzinfo=TZ),
        fatigue_level="high",
    )

    availability = calculate_availability(
        date(2026, 5, 19),
        date(2026, 5, 19),
        class_sessions=[],
        work_shifts=[shift],
        timezone=TZ,
    )

    morning = availability.days[0].study_windows[0]
    assert morning.max_intensity == "light"
    assert morning.start_at.hour >= 10
```

- [ ] **Step 3: Add failing planner intensity tests**

Add to `tests/academic/test_planner.py`:

```python
def test_high_fatigue_day_only_schedules_light_or_recovery_blocks() -> None:
    plan = _plan(
        assignments=[_assignment("Essay", "a", estimated_hours=2)],
        windows=[_window("10:00", "13:00", max_intensity="light")],
    )

    assert plan.blocks
    assert {block.intensity for block in plan.blocks} <= {"light", "recovery"}


def test_heavy_week_reduces_total_planned_minutes() -> None:
    assignment = _assignment("Large", "a", estimated_hours=20)
    light_week = _plan(
        assignments=[assignment],
        windows=[_window("09:00", "17:00")],
        settings=PlanningSettings(max_block_minutes=240, break_between_blocks_minutes=0),
    )
    heavy_week = _plan(
        assignments=[assignment],
        windows=[_window("09:00", "17:00", max_intensity="light")],
        settings=PlanningSettings(max_block_minutes=240, break_between_blocks_minutes=0),
    )

    assert heavy_week.summary.total_planned_minutes <= light_week.summary.total_planned_minutes * 0.7
```

- [ ] **Step 4: Add intensity fields to models**

In `core/academic/models.py`, add `max_intensity: str = "deep"` to `StudyWindow` and `intensity: str = "medium"` to `PlannedStudyBlock` equivalent models if they live there. Keep accepted values `recovery`, `light`, `medium`, `deep`.

- [ ] **Step 5: Implement availability fatigue caps**

In `core/academic/availability.py`, add a helper:

```python
def _max_intensity_for_window(start_at: datetime, work_shifts: list[WorkShift]) -> str:
    previous_late_high = any(
        shift.fatigue_level == "high"
        and shift.end_at.date() == start_at.date() - timedelta(days=1)
        and shift.end_at.hour >= 23
        for shift in work_shifts
    )
    if previous_late_high and start_at.hour < 10:
        return "light"
    same_day_high = any(
        shift.fatigue_level == "high" and shift.start_at.date() == start_at.date()
        for shift in work_shifts
    )
    if same_day_high:
        return "light"
    return "deep"
```

Pass `work_shifts` into `_free_windows` and set `StudyWindow(max_intensity=...)` in `_append_window`.

- [ ] **Step 6: Implement planner intensity assignment**

In `core/academic/planner.py`, add intensity to `PlannedStudyBlock` and map window caps:

```python
def _block_intensity(window: _PlanningWindow) -> str:
    cap = getattr(window, "max_intensity", "deep")
    if cap in {"recovery", "light", "medium", "deep"}:
        return cap
    return "medium"
```

When creating `_PlanningWindow`, copy `window.max_intensity`. When appending `PlannedStudyBlock`, set `intensity=_block_intensity(window)`.

- [ ] **Step 7: Run planning tests**

Run:

```bash
.venv/bin/pytest tests/academic/test_availability.py tests/academic/test_planner.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add docs/DECISIONS.md docs/REQUIREMENTS.md docs/PRODUCT_SPEC.md core/academic/models.py core/academic/availability.py core/academic/planner.py tests/academic/test_availability.py tests/academic/test_planner.py
git commit -m "feat: enforce fatigue-aware planning"
```

### Task 8: Centralize LLM Call Logging

**Files:**
- Create: `core/llm/audit.py`
- Modify: `core/llm/service.py`
- Modify: `core/retrieval/service.py`
- Modify: `core/nl/agent.py`
- Modify: `app/bot.py`
- Modify: `app/dashboard.py`
- Modify: `tests/llm/test_llm_service.py`
- Modify: `tests/test_nl_agent_loop.py`
- Modify: `tests/retrieval/test_retrieval_service.py`

- [ ] **Step 1: Add audit helper tests**

Create `tests/llm/test_llm_audit.py`:

```python
import json
from pathlib import Path

from core.llm.audit import log_llm_call


def test_log_llm_call_writes_metadata_only(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "llm_calls.jsonl"

    log_llm_call(
        path,
        provider="local",
        model="test-model",
        task_type="agent_turn",
        success=True,
        latency_ms=12,
        input_tokens=10,
        output_tokens=3,
        error=None,
    )

    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["provider"] == "local"
    assert payload["model"] == "test-model"
    assert payload["task_type"] == "agent_turn"
    assert "prompt" not in payload
    assert "response" not in payload
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/pytest tests/llm/test_llm_audit.py -q
```

Expected: FAIL because `core.llm.audit` does not exist.

- [ ] **Step 3: Implement `core/llm/audit.py`**

```python
"""Metadata-only LLM call audit logging."""

from __future__ import annotations

import json
from pathlib import Path

from core.utils import utc_now


def log_llm_call(
    path: Path | str | None,
    *,
    provider: str,
    model: str,
    task_type: str,
    success: bool,
    latency_ms: int | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> None:
    if path is None:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": utc_now(),
        "event_type": "llm_call",
        "provider": provider,
        "model": model,
        "task_type": task_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "success": success,
        "latency_ms": latency_ms,
        "outcome": "success" if success else "error",
        "error": error,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Inject log path into agent and retrieval services**

Add `llm_log_path` to `AgentLoop.__init__` and `RetrievalService.__init__`; pass `settings.llm_log_path` from `app/bot.py`, `app/dashboard.py`, and command builders.

- [ ] **Step 5: Replace local ad hoc logging**

In `core/llm/service.py`, replace `_log_call` body with `log_llm_call(...)`.

In `core/nl/agent.py`, wrap `client.generate` timing with `time.perf_counter()` and call:

```python
log_llm_call(
    self.llm_log_path,
    provider="local",
    model=response.model,
    task_type="agent_turn",
    success=True,
    latency_ms=latency_ms,
)
```

On LLM exceptions, log `success=False`.

In `core/retrieval/service.py`, log `task_type="retrieval_answer"`.

- [ ] **Step 6: Run LLM/retrieval tests**

Run:

```bash
.venv/bin/pytest tests/llm tests/retrieval/test_retrieval_service.py tests/test_nl_agent_loop.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/llm/audit.py core/llm/service.py core/retrieval/service.py core/nl/agent.py app/bot.py app/dashboard.py tests/llm/test_llm_audit.py tests/llm/test_llm_service.py tests/retrieval/test_retrieval_service.py tests/test_nl_agent_loop.py
git commit -m "fix: centralize llm audit logging"
```

---

## Cycle 3: Architecture Cleanup

### Task 9: Make `retrieval_chunks` Schema Single-Owned

**Files:**
- Modify: `core/db.py`
- Modify: `core/retrieval/vector_store.py`
- Modify: `tests/test_db.py`
- Modify: `tests/retrieval/test_retrieval_service.py`

- [ ] **Step 1: Add a schema ownership test**

Add to `tests/test_db.py`:

```python
def test_retrieval_chunks_schema_owned_by_core_db() -> None:
    from core.retrieval import vector_store

    assert not hasattr(vector_store, "SCHEMA_SQL")
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_db.py::test_retrieval_chunks_schema_owned_by_core_db -q
```

Expected: FAIL because `core.retrieval.vector_store.SCHEMA_SQL` exists.

- [ ] **Step 3: Remove duplicate schema from vector store**

Delete `SCHEMA_SQL` from `core/retrieval/vector_store.py`.

Change `ensure_schema` to:

```python
    def ensure_schema(self) -> None:
        from core.db import init_db

        init_db(self.db_path)
```

- [ ] **Step 4: Run retrieval and DB tests**

Run:

```bash
.venv/bin/pytest tests/test_db.py tests/retrieval/test_retrieval_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/db.py core/retrieval/vector_store.py tests/test_db.py tests/retrieval/test_retrieval_service.py
git commit -m "refactor: single-own retrieval chunk schema"
```

### Task 10: Quarantine Legacy `NLRouter`

**Files:**
- Modify: `core/nl/router.py`
- Modify: `app/bot.py`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/AGENT_LOOP.md`
- Modify: `tests/test_nl_router.py`
- Modify: `tests/test_nl_classifier.py`

- [ ] **Step 1: Add architecture decision**

Append to `docs/DECISIONS.md`:

```markdown
## 2026-05-21 — NL Architecture

The canonical natural-language path is `AgentLoop` plus `ToolRegistry`.
`NLRouter` and `NLClassifier` are legacy compatibility surfaces only. New safety,
tooling, and product behavior must land in `ToolRegistry`, not in `NLRouter`.
```

- [ ] **Step 2: Remove unused app factory**

Delete `_build_nl_router` from `app/bot.py`.

- [ ] **Step 3: Mark legacy modules explicitly**

At the top of `core/nl/router.py`, update the module docstring:

```python
"""Legacy fixed-intent NL router.

The canonical Telegram natural-language path is AgentLoop + ToolRegistry.
Do not add new product behavior here; migrate behavior to tools instead.
"""
```

- [ ] **Step 4: Update docs**

In `docs/ARCHITECTURE.md`, replace the implementation priority that says to replace `core/nl/` with:

```markdown
1. Keep `AgentLoop` + `ToolRegistry` as the canonical NL path; quarantine
   `NLRouter`/`NLClassifier` as legacy test compatibility until removed.
```

In `docs/AGENT_LOOP.md`, replace “All items from the original punch list have been shipped” with:

```markdown
The canonical tool-agent loop is present, but legacy classifier/router modules
remain as compatibility code until their tests are migrated.
```

- [ ] **Step 5: Add no-new-use test**

Add to `tests/test_bot.py`:

```python
def test_bot_does_not_build_legacy_nl_router() -> None:
    import app.bot as bot

    assert not hasattr(bot, "_build_nl_router")
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/test_bot.py tests/test_nl_agent_loop.py tests/test_nl_router.py tests/test_nl_classifier.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot.py core/nl/router.py docs/DECISIONS.md docs/ARCHITECTURE.md docs/AGENT_LOOP.md tests/test_bot.py tests/test_nl_router.py tests/test_nl_classifier.py
git commit -m "docs: quarantine legacy nl router"
```

### Task 11: Split The Telegram Adapter

**Files:**
- Create: `app/telegram_auth.py`
- Create: `app/telegram_formatters.py`
- Create: `app/telegram_services.py`
- Create: `app/telegram_notifications.py`
- Modify: `app/bot.py`
- Modify: `tests/test_bot.py`
- Modify: command tests under `tests/test_*_commands.py`

- [ ] **Step 1: Move allowlist helpers**

Create `app/telegram_auth.py`:

```python
"""Telegram authorization helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AllowlistFilter:
    """Allow only configured Telegram user IDs through to handlers."""

    def __init__(self, allowed_user_ids: Sequence[int] | None = None) -> None:
        self._allowed_user_ids = set(allowed_user_ids) if allowed_user_ids is not None else None

    def check_update(self, update) -> bool:
        return self.filter(update)

    def filter(self, update) -> bool:
        user = update.effective_user
        user_id = user.id if user is not None else None
        allowed_user_ids = self._allowed_user_ids
        if allowed_user_ids is None:
            allowed_user_ids = set(get_settings().TELEGRAM_ALLOWED_USER_IDS)
        if user_id is not None and user_id in allowed_user_ids:
            return True
        logger.warning(
            "blocked_telegram_update",
            extra={"event_type": "blocked_telegram_update", "user_id": user_id},
        )
        return False


def telegram_user_authorized(settings: Settings, user_id: int | None) -> bool:
    allowed_user_ids = getattr(settings, "TELEGRAM_ALLOWED_USER_IDS", [])
    if not isinstance(allowed_user_ids, Sequence) or isinstance(allowed_user_ids, (str, bytes)):
        return False
    if not allowed_user_ids:
        return False
    return user_id is not None and user_id in set(allowed_user_ids)
```

Update imports in `app/bot.py` and tests.

- [ ] **Step 2: Move service builders**

Create `app/telegram_services.py` with `_get_bot_settings`, `build_retrieval_service`, `build_llm_service`, `build_nl_tool_registry`, and `build_nl_agent`. Rename helpers without leading underscores when imported into `bot.py`.

- [ ] **Step 3: Move formatting helpers**

Create `app/telegram_formatters.py` with `_format_today`, `_format_week`, `_format_plan`, `_format_retrieval_answer`, `_format_local_llm_error_lines`, and related pure formatting helpers. Export names without leading underscores where practical.

- [ ] **Step 4: Move notification loops**

Create `app/telegram_notifications.py` with `_start_notification_tasks`, `_cancel_notification_tasks`, `_run_deadline_alert_loop`, `_run_overdue_check_loop`, `_run_study_reminder_loop`, `_run_weekly_review_loop`, and notification send helpers.

- [ ] **Step 5: Keep `app/bot.py` as wiring plus handlers**

After moves, `app/bot.py` should contain command handlers, `build_application`, `start_bot`, `stop_bot`, and `_reply`. Target size after this task: under 800 lines. Do not force under 500 in this task if that requires risky command extraction.

- [ ] **Step 6: Run Telegram tests**

Run:

```bash
.venv/bin/pytest tests/test_bot.py tests/test_data_commands.py tests/test_schedule_commands.py tests/test_retrieval_commands.py tests/test_llm_commands.py tests/test_notification_commands.py tests/test_planning_commands.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot.py app/telegram_auth.py app/telegram_services.py app/telegram_formatters.py app/telegram_notifications.py tests/test_bot.py tests/test_data_commands.py tests/test_schedule_commands.py tests/test_retrieval_commands.py tests/test_llm_commands.py tests/test_notification_commands.py tests/test_planning_commands.py
git commit -m "refactor: split telegram adapter responsibilities"
```

---

## Final Verification

- [ ] **Step 1: Run import timing smoke check**

Run:

```bash
.venv/bin/python -c "import time; t=time.perf_counter(); from app.config import Settings; print(round(time.perf_counter()-t, 3))"
```

Expected: prints a duration under `2.0`. If it is higher, profile imports before claiming the branch is ready.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass. The previous audit attempt reached no tests in `258.70s`; this must be fixed before merging.

- [ ] **Step 3: Run focused security regression suite**

Run:

```bash
.venv/bin/pytest tests/test_path_policy.py tests/test_local_transport.py tests/test_policy_engine.py tests/test_nl_agent_loop.py -q
```

Expected: PASS.

- [ ] **Step 4: Review docs for contradictions**

Run:

```bash
rg -n "all items.*shipped|fixed intent|user_id=0|0\\.0\\.0\\.0|arbitrary|target contract|implementation differs" docs README.md CLAUDE.md
```

Expected: every remaining hit is either historical context or an explicit, current warning. Update docs if any hit contradicts shipped behavior.

- [ ] **Step 5: Final status**

Run:

```bash
git status --short
```

Expected: only intentional changes remain.

---

## Self-Review

Spec coverage:

- File access security: Task 1.
- Mutation governance and action audit: Tasks 2, 3, and 4.
- Web/Ollama egress: Tasks 4 and 5.
- Local-only dashboard/API: Task 5.
- Plain-message allowlist default-deny: Task 6.
- Planning fatigue/spec gap: Task 7.
- LLM logging: Task 8.
- Retrieval schema ownership: Task 9.
- Legacy NL architecture: Task 10.
- Oversized Telegram adapter: Task 11.
- Slow or stuck verification: Final Verification.

Placeholder scan: no open-ended placeholder steps are intentionally left. Each code-changing task includes test-first steps and exact commands.

Type consistency: new settings are `knowledge_file_roots`, `allow_external_ollama`, and `allow_non_loopback_clients`; new policy actions are `write_memory`, `update_memory`, and `web_search`.
