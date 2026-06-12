# Atenas V1 Defect And Governance Closure Spec

## Purpose

A full read-only audit on 2026-06-11 compared every canonical doc against the
implementation. This spec turns the audit's defects into required code
changes. It is the current priority phase in `docs/superpowers/README.md` and
must land before feature work (model profile config, prompt budgets, trace
replay).

Doc-side drift found by the same audit was already fixed on 2026-06-12
(`docs/DATA_MODEL.md` rewritten against `core/db.py`, `docs/AGENT_LOOP.md`
web-category and known-gap notes, `docs/SECURITY.md` non-compliance record,
`docs/SCHEMAS.md` cross-references). This spec is code and tests only.

Authority: where this spec and the canonical docs describe behavior, the
canonical docs win (`docs/AGENT_LOOP.md` for agent behavior, `docs/SECURITY.md`
for security posture). This spec describes how to make the code comply.

## Ground Rules For Implementation

- Keep changes small and reviewable; one work package per PR is the intended
  granularity.
- Tests mock LLM providers and use isolated settings/databases. No fix may
  depend on a live Ollama.
- Do not add behavior to `NLRouter`/`NLClassifier`; all agent fixes land in
  `AgentLoop`/`ToolRegistry`.
- Update `docs/AGENT_LOOP.md` "Known gaps", `docs/SECURITY.md` "Known
  non-compliance", `docs/ARCHITECTURE.md`, and `docs/PRODUCT_SPEC.md` snapshot
  notes as each gap closes — those sections list exactly these defects.

---

## WP1 — Agent tool crash and output defects (HIGH)

### WP1.1 Missing `date` import crashes two tools

`core/nl/tools.py` uses `date.fromisoformat(...)` and `date.today()` in
`_tool_get_availability` (~line 859) and `_tool_generate_study_plan`
(~line 936) without importing `datetime.date`. Every call raises `NameError`.

Required behavior:

- Import `date` (and use the service timezone, not naive `date.today()`, if
  the academic service exposes a timezone-aware "today" — match how slash
  commands compute today).
- Invalid `start_date`/`end_date`/`reference_date` strings must return a
  structured tool error ("Invalid date: ..."), not raise `ValueError`.

### WP1.2 Tool handler exceptions must not escape the registry

`ToolRegistry.run_tool` does not catch handler exceptions, and `AgentLoop.run`
does not either, so an unexpected exception aborts the Telegram handler and
the user gets silence.

Required behavior:

- `ToolRegistry.run_tool` wraps `tool.handler(...)` in a try/except that
  returns a failed `StructuredToolResult` ("Tool failed: <tool_name>"),
  logs the exception with `event_type=tool_handler_exception`, and never
  exposes a stack trace to Telegram.
- The agent loop's existing `tool_error` path then produces the normal
  "Nothing else changed." reply.

### WP1.3 `get_local_llm_status` always reports unreachable

`_tool_get_local_llm_status` calls `engine.generate("test", max_tokens=1)`
(`OllamaEngine.generate` takes no `max_tokens`) and reads `engine.base_url`
(attribute does not exist). Both errors are swallowed by `except Exception`,
so the tool reports "unreachable" even when Ollama is healthy.

Required behavior:

- Use `OllamaEngine.health()` (which calls `list_models`) instead of a
  generation probe. Report availability, configured model, and whether the
  configured model is present in the model list.
- Do not catch bare `Exception` around the whole handler; rely on
  `EngineHealth.error`.

### WP1.4 Minutes formatted with `// 2` instead of `// 60`

Six agent tools format minutes as hours with `// 2` / `% 2` (e.g.
`core/nl/tools.py` ~lines 811, 829, 836–838, 877, 946–949, 969–971), so 120
minutes renders "60h00".

Required behavior:

- Add one shared duration formatter in the tool layer (or reuse the
  `divmod(minutes, 60)` pattern from `app/bot.py::_format_duration`) and use
  it everywhere in `core/nl/tools.py`. No `// 2` arithmetic remains.

### WP1.5 Trace steps record the wrong latency

`AgentLoop._record_step` passes the LLM decision latency as the tool step
`latency_ms` (`core/nl/agent.py` ~line 208).

Required behavior:

- Time the `registry.run_tool` call and record that duration as the step
  latency. The LLM latency stays on the `llm_calls` log only.

Acceptance criteria (WP1):

- New tests execute `get_availability` (no args and with explicit dates),
  `generate_study_plan` (with and without `reference_date`), and an
  invalid-date case through `ToolRegistry.run_tool` against a seeded temp DB;
  all return `ok=True`/structured errors, never raise.
- A test registers a handler that raises and asserts `run_tool` returns
  `ok=False` without propagating.
- A test with a mocked engine asserts `get_local_llm_status` reports
  reachable + model presence; a connection-refused mock reports unreachable.
- A formatting test asserts 120 minutes renders as `2h00` in today/week/
  availability/plan/deadline-risk tool messages.

---

## WP2 — Governance: policy and audit on every act (HIGH)

### WP2.1 Auto-tier `add_*` tools bypass the policy engine

`_tool_add_assignment`, `_tool_add_note`, `_tool_add_class_session`, and
`_tool_add_work_shift` call core services directly. They never build an
`ActionProposal`, never pass `PolicyEngine.check`, and never emit the
`action_executed` audit record. This violates FR-00/FR-04, AGENT_POLICY's
auto-tier flow, and the architecture governance stages. The policy allowlist
already contains all four action types.

Required behavior:

- Route all four through `_gate_action` with `tier=ActionTier.AUTO`,
  `criticality=ActionCriticality.LOCAL_WRITE`, registering executor handlers
  (`_execute_add_assignment`, etc.) exactly like `set_assignment_status`.
- Module-reference resolution stays in the tool handler (before the gate),
  so the proposal payload carries stable IDs only.
- Validation failures from the service remain structured tool errors.

Acceptance criteria:

- A test spies on `PolicyEngine.check` (or injects a deny-all engine) and
  asserts each `add_*` tool consults policy and respects a deny.
- A log-capture test asserts an `action_executed` record with
  `action_type=add_assignment` (etc.), actor, and payload summary is emitted
  on success.
- Existing `add_work_shift` fatigue-level tests keep passing.

### WP2.2 Pending actions marked `executed` regardless of outcome

`app/bot.py` (~lines 204–213) marks the durable pending record `executed`
after a `yes` even when policy blocks the action, the handler errors, or
`execute_pending` rejects an actor mismatch.

Required behavior:

- Inspect the `StructuredToolResult` from `execute_pending`:
  - executed successfully → `executed`;
  - policy denied / handler error → `failed` (new status value) with the
    failure message relayed to the user;
  - actor mismatch → `cancelled`.
- `AgentRuntimeStore.mark_pending_action` accepts the new status; `/pending`
  ignores non-`pending` records as today.
- User-facing replies distinguish "executed" from "blocked/failed" (FR-04).

Acceptance criteria:

- Tests cover all three outcomes by stubbing the executor: confirm → blocked
  by policy leaves status `failed` and replies with the policy reason;
  confirm → success leaves `executed`; actor mismatch leaves `cancelled`.

### WP2.3 `/confirm` command

`docs/AGENT_LOOP.md` and `docs/SECURITY.md` promise `yes` / `/confirm`; no
`/confirm` handler exists (a `/confirm` message routes to `unknown_command`).

Required behavior:

- Register `/confirm` (allowlist-filtered) as a deterministic equivalent of
  replying `yes` to the active durable pending action, sharing one code path
  with the plain-text confirmation (including WP2.2 status handling).
- Add `/confirm` to `core/command_catalog.py` (Core group) with a
  command-only parity rationale, and to `docs/COMMAND_TOOL_PARITY.md`.
- With no pending action, `/confirm` replies "No pending action."

Acceptance criteria:

- Tests: `/confirm` executes a seeded pending action; `/confirm` with no
  pending action replies safely; parity test passes with the new entry.

### WP2.4 Command audit logging (FR-10)

Slash-command handlers and `SkillRegistry.dispatch` emit no per-command audit
events, violating FR-10 ("System MUST log commands") and PRODUCT_SPEC success
criterion 17.

Required behavior:

- Emit one structured log event per handled command —
  `event_type=command_executed` with timestamp, actor user ID, command name,
  and success/failure — from a single shared point (a decorator or a small
  wrapper used at handler registration), not 40 copy-pasted logger calls.
- Never log full argument payloads for note/file bodies; reuse the redaction
  conventions from `core/action_executor.py`.
- `SkillRegistry.dispatch` logs dispatches the same way and drops the
  `user_id: int = 0` default (make `user_id` required; the API passes `-1`).

Acceptance criteria:

- A log-capture test asserts `/status` and one write command produce
  `command_executed` events with actor and command fields, and that note
  bodies do not appear in the event.

### WP2.5 Local-only guard must not trust `X-Forwarded-For`

`app/main.py` (~lines 78–87) reads `X-Forwarded-For` first and allows the
request if that client-controlled value is loopback. A remote client can send
`X-Forwarded-For: 127.0.0.1` to bypass the guard exactly when it matters
(accidental non-loopback bind).

Required behavior:

- Base the allow decision on `request.client.host` (the socket peer) only.
- `X-Forwarded-For` may only make the decision stricter: if the socket peer
  is loopback but a forwarded header names a non-loopback client, deny (this
  preserves protection behind a local reverse proxy).
- Keep the `testclient` allowance and the `allow_non_loopback_clients`
  escape hatch.

Acceptance criteria:

- Tests: spoofed `X-Forwarded-For: 127.0.0.1` from a non-loopback peer is
  denied; loopback peer with non-loopback `X-Forwarded-For` is denied;
  loopback peer with no header is allowed; existing dashboard/API tests pass.

---

## WP3 — Telegram boundary validation

### WP3.1 `/add_shift` crashes on non-numeric energy

`app/bot.py` (~line 394) calls `int(energy)` unguarded; `/add_shift ...
energy=abc` raises and the user gets silence.

Required behavior:

- Parse defensively (mirror the guarded priority parse) and reply with the
  usage message ("energy must be a number 1-5") on bad input. The service's
  range validation continues to handle out-of-range integers.

Acceptance criteria:

- A test sends `/add_shift` with `energy=abc` and asserts a usage reply and
  no exception; a valid shift still persists.

---

## WP4 — Performance and resource hygiene

### WP4.1 Retrieval sync re-reads every file on every query

`RetrievalService.retrieve_sources` calls `sync_index` on every query, which
re-chunks every note and re-reads every registered file (up to 120 KB each)
just to compare freshness, and `_sync_fts` rebuilds the whole FTS table when
any single source changed.

Required behavior:

- Decide staleness from metadata before reading content: compare the stored
  `updated_at` per source (one SQL query for all sources) against the
  repository rows, and only chunk/read sources whose `updated_at` differs or
  which are missing from the index. File content is read only for stale
  files.
- Replace the global `_sync_fts` delete/rebuild with per-source FTS row
  deletes/inserts inside `replace_source` and `delete_stale_sources`.
  `rebuild()` may keep the full rewrite.
- Observable behavior (which sources are retrievable, lexical fallback,
  archived exclusion) is unchanged; existing retrieval tests must pass.

Acceptance criteria:

- A test indexes N sources, instruments file reads (e.g. monkeypatched
  `_read_registered_text_file`), runs a second query with no changes, and
  asserts zero file reads; editing one note triggers exactly one re-index.

### WP4.2 SQLite connections are never closed

`with get_connection(...)` commits but does not close (sqlite3 context
manager semantics) across `core/memory_manager.py`, `core/nl/runtime_state.py`,
`core/nl/traces.py`, and `core/retrieval/vector_store.py`.

Required behavior:

- Make closing structural: either have `get_connection` return a
  `contextlib.closing`-style wrapper used uniformly, or add a small
  `connect()` context manager in `core/db.py` that commits/rolls back and
  closes, and migrate the call sites. Pick one mechanism; do not hand-patch
  each site with try/finally.

Acceptance criteria:

- A test asserts the connection returned by the new helper is closed after
  the block (e.g. subsequent `execute` raises `ProgrammingError`).

### WP4.3 Backup of a live WAL database

`BackupService.create_backup` copies `data/atenas.sqlite` byte-wise; with WAL
mode active, un-checkpointed `-wal` content is silently omitted.

Required behavior:

- Snapshot through SQLite instead of the filesystem: use
  `sqlite3.Connection.backup()` (or `VACUUM INTO`) to a temp file and archive
  that, so the backup is a consistent checkpointed image.

Acceptance criteria:

- A test writes rows, leaves the connection open (WAL not checkpointed),
  creates a backup, restores to a fresh path, and asserts the rows exist.

---

## WP5 — Dead code, packaging, and dependency hygiene

### WP5.1 Remove dead duplicate Telegram helper modules

`app/telegram_auth.py`, `app/telegram_formatters.py`,
`app/telegram_services.py`, and `app/telegram_notifications.py` duplicate
logic that `app/bot.py` implements inline and are imported by nothing
(only by each other). FR-11 requires dead modules be implemented, documented
as reserved, or removed.

Required behavior:

- Remove the four modules. If any contains behavior `bot.py` lacks, port it
  first; do not keep two copies. (The roadmap's future `bot.py` split can
  reintroduce real modules with `bot.py` as the single source.)

### WP5.2 Remove docstring-only stubs

`core/embedding_manager.py`, `core/graph_manager.py`,
`core/retrieval_engine.py`, and `app/scheduler.py` are docstring-only stubs
referencing superseded phases (`core/retrieval/` and the bot's asyncio jobs
are the real implementations).

Required behavior:

- Remove all four. `nodes`/`edges` tables stay (documented as reserved in
  `docs/DATA_MODEL.md`); the stub *modules* are not referenced anywhere.

### WP5.3 Dependency declarations drift

`requirements.txt` is missing `click`, which `app/cli.py` imports and
`pyproject.toml` declares.

Required behavior:

- Add `click==8.x` (pin to the version in use) to `requirements.txt`. Add a
  packaging test asserting every `[project] dependencies` name appears in
  `requirements.txt` (version pins may differ in strictness).

### WP5.4 Remove the empty `web/templates` directory

Dashboard templates live in `app/templates/`; `web/` is empty residue and
excluded from packaging.

Acceptance criteria (WP5):

- `grep` finds no references to the removed modules; the full suite passes;
  `pip install -e . --no-deps --dry-run` still succeeds;
  `tests/test_packaging.py` extended per WP5.3.

---

## WP6 — Toolset markers and visibility

`core/nl/toolsets.py` unlocks the destructive/egress toolsets only when the
message contains English markers ("delete", "remove", "web", ...). The
product's own docs quote the user in Portuguese; a Portuguese request
("apagar os módulos duplicados") never sees the destructive tools.

Required behavior:

- Extend `DESTRUCTIVE_REQUEST_MARKERS` and `EGRESS_REQUEST_MARKERS` with the
  Portuguese equivalents (at minimum: apagar, deletar, excluir, remover,
  arquivar, limpar, duplicado/duplicar for destructive; pesquisar, buscar na
  internet/web, "na internet", "online" for egress) and the bare "merge"
  marker.
- Keep selection deterministic and code-owned; the model still cannot expand
  its own toolsets.
- Document the marker mechanism's contract in `docs/AGENT_LOOP.md` (the
  "Toolset visibility" note added 2026-06-12 already names the mechanism;
  update the known-gaps list when this lands).

Acceptance criteria:

- Tests assert Portuguese destructive phrasing selects
  `TELEGRAM_DESTRUCTIVE`, Portuguese web phrasing selects `TELEGRAM_EGRESS`
  only when `web_enabled=True`, and neutral messages select only
  `TELEGRAM_SAFE`.

---

## Suggested Order

1. WP1 (crashes and wrong output — user-visible correctness).
2. WP2 (policy/audit/guard — governance and security compliance).
3. WP3 (boundary validation).
4. WP5 (cleanup — shrinks the surface the other fixes touch; can also run
   first if preferred, it is independent).
5. WP4 (performance/resources).
6. WP6 (toolset markers).

Each WP closes its bullet in `docs/AGENT_LOOP.md` "Known gaps" and
`docs/SECURITY.md` "Known non-compliance"; the final WP removes both
sections' entries entirely and updates `docs/superpowers/README.md` phase
status to Done.

## Out Of Scope

- New features (model profile config, prompt budgets, trace replay, approved
  skill memory) — tracked separately in the roadmap.
- Semantic/embedding search (post-v1, see `docs/DATA_MODEL.md`).
- Splitting `app/bot.py` / `core/nl/tools.py` beyond what the fixes require
  (the roadmap's refactor-support section governs that).
- Authentication for dashboard/API or any remote exposure.

## Completion Definition

This spec is complete when:

1. Every acceptance criterion above has a passing automated test.
2. `docs/AGENT_LOOP.md` "Known gaps" and `docs/SECURITY.md` "Known
   non-compliance" sections are empty/removed because the code complies.
3. The full suite passes with mocked LLM providers.
4. The roadmap phase row is marked Done.
