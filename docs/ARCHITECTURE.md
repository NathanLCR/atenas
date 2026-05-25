# Atenas — Architecture

## Status

Target architecture as of 2026-05-20, refreshed against the implementation on
2026-05-24. This is the current contract for new work; legacy compatibility
surfaces are called out explicitly below.

## Guiding Principle

```text
The LLM is a tool-calling agent with strong tools.
Deterministic systems validate and do the heavy lifting.
The human approves only what deletes or leaves the machine.
Everything that changes is logged.
```

Atenas is a **tool-calling agent loop**, not a fixed intent classifier. The LLM
receives structured tools, calls one, observes the structured result, and
decides the next step — carrying the user's goal across iterations and turns. It
never executes application logic directly: tool arguments are validated,
natural-language references are resolved to stable IDs, the action tier is
enforced by code, and services own the business logic. The canonical behavior
contract is `docs/AGENT_LOOP.md`; this file describes the architecture that
realizes it.

## Governance Model

Action handling has four stages, but the **approval** stage is tiered — most
writes are not gated:

| Stage | Owner | Responsibility |
|---|---|---|
| Decide | LLM/tool agent | Interpret the request and choose a tool/action with arguments |
| Validate | Deterministic code | Validate schema, resolve IDs, check domain constraints, compute safe options |
| Gate | Code plus policy | Classify the action tier; auto-run reversible local writes, hold destructive/egress for human confirmation, deny forbidden actions |
| Execute | Core service | Mutate state, then emit an audit record of what changed |

Action tiers:

- **Auto** — reversible, local, low-risk writes (add/update note, set status,
  add class/shift) execute directly and are logged.
- **Confirm-first** — destructive (delete, clear, bulk-remove) and egress
  (external message, export, sensitive external-LLM) require explicit human
  confirmation before execution.
- **Forbidden** — shell, source edits, secret reads, unrestricted filesystem are
  blocked unconditionally; unknown actions default-deny.

The tier is decided by code from the tool's declared category. The model cannot
set confirmation flags or change its own tier.

## Deployment Posture

Atenas is local-running and single-user by default.

- Telegram is the primary user interface.
- Dashboard and REST API are local support surfaces and should bind to
  `127.0.0.1`.
- SQLite, files, and logs stay on the local machine.
- Local Ollama is the default LLM provider.
- External LLM providers are opt-in and must be treated as data egress.

## High-Level Flow

```text
Telegram user
    |
    v
Telegram bot allowlist
    |
    v
Conversation orchestrator
    |
    +-- Slash command router --------------------+
    |                                            |
    v                                            v
LLM agent loop                             Existing command handlers
    |   ^
    |   |  (observe result, decide next step)
    v   |
Tool registry (read / compute / act)
    |
    v
Deterministic validation + ID resolution
    |
    v
Action-tier gate
    |  auto -> execute        (reversible local writes)
    |  confirm-first -> hold  (destructive / egress, wait for "yes")
    |  forbidden -> deny
    v
Policy engine
    |
    v
Application services in core/
    |
    v
Repositories
    |
    v
SQLite / local files / JSONL audit logs
```

Local dashboard/API paths are side channels into the same services. They are
not the primary product interface and must not become unauthenticated remote
surfaces.

## Layer Responsibilities

### `app/`

Application shell only:

- Telegram update handling and response formatting.
- Local FastAPI routes and dashboard rendering.
- Configuration loading and dependency wiring.
- Startup validation for enabled transports, especially Telegram allowlist.

`app/` may depend on `core/`. `core/` must not depend on `app/`.

### `core/`

Domain and application logic:

- Academic scheduling, assignments, availability, and planning.
- Knowledge notes/files/search/retrieval.
- LLM client/service abstractions (with an engine interface wrapping
  OllamaClient that exposes `generate`, `health`, `list_models`).
- Policy engine and action execution.
- Database schema and repository access.

Core services receive configuration and dependencies through constructors or
method parameters. They do not import `app.config`.

### `tools/` or equivalent tool layer

The LLM-facing tool layer is the bridge between conversation and capabilities.
It should be thin and explicit:

- Defines tool names, descriptions, argument schemas, and result schemas.
- Calls existing services; it does not duplicate service behavior.
- Declares each tool's category (read / compute / act) and action tier.
- Auto-tier acts execute directly; confirm-first acts produce a pending proposal.
- Resolves natural-language labels to stable IDs before execution.

If this layer lives under an existing package initially, keep the same
responsibilities and dependency direction.

### `skills/`

Legacy command handlers and reusable command surfaces. They may remain as
slash-command implementations, but shared behavior should migrate toward
services/tools instead of being copied into Telegram-specific formatting.

## Tool Categories

| Category | Examples | Execution rule |
|---|---|---|
| Read / search | status, today, week, deadlines, modules, assignments, notes, files, retrieval sources | May run after Telegram allowlist auth |
| Compute / cross-reference | generate plan, suggest next task, explain deadline risk, **detect duplicate modules** | May run after auth; deterministic service does the computation |
| Act (auto) | add assignment, set status, set hours, add note, add class, add shift | Agent executes directly after validation; outcome is audit-logged |
| Act (confirm-first) | delete/clear/bulk-remove, deduplicate, archive, send external message, export | Code holds a pending proposal; executes only after explicit `yes` |
| Web (guarded) | web search/fetch | Opt-in, disabled by default; egress + untrusted content; never auto-acts on returned text |
| System | local LLM status, app health, configuration summary | Read-only; never reveal secrets |

## Read Flow

```text
User: "what should I study today?"
  -> allowlist check
  -> LLM chooses get_today_overview + list_due_assignments
  -> tools return structured results
  -> LLM writes concise Telegram answer
```

Read tools return structured data. The LLM can decide presentation, but it
cannot bypass service validation or fetch arbitrary filesystem content.

## Write Flow

Reversible local write (auto tier):

```text
User: "mark my ML essay done"
  -> allowlist check
  -> agent calls find_assignment(title="ML essay")  [read]
  -> agent calls set_assignment_status(id="...", status="done")  [act, auto]
  -> code validates ID/status, confirms the tier is auto
  -> policy engine checks the action
  -> service executes the update
  -> audit log records what changed
  -> agent confirms in plain Telegram text
```

Destructive write (confirm-first tier):

```text
User: "delete my duplicate modules"
  -> agent calls detect_duplicate_modules()  [compute] -> finds the duplicates
  -> agent calls delete_modules(ids=[...])  [act, confirm-first]
  -> code validates IDs, sees confirm-first tier, builds a pending proposal
  -> bot shows the exact modules and asks for confirmation
  -> user replies "yes"
  -> policy engine checks the action
  -> service executes the delete
  -> audit log records what changed
```

Auto-tier writes execute directly; the audit log is the safety net. Destructive
and egress actions must never execute from the LLM response alone — they require
explicit confirmation through a policy-checked path. The model cannot
self-classify an action as auto.

No router, tool adapter, dashboard route, or API route may execute a
confirm-first action merely because the LLM produced plausible arguments.
Mutation authority belongs to core services after the governance stages above.

## Retrieval Flow

```text
User: "what do my notes say about CNNs?"
  -> retrieve sources from registered, non-archived notes/files
  -> if no sources, return no-source fallback
  -> if sources exist, call local LLM with delimited sources
  -> return answer with source labels
```

Retrieval indexing should be incremental, explicit, or dirty-flagged. Querying
must not rebuild the full chunks table on every request.

## Storage

| Data | Location |
|---|---|
| Academic state | SQLite |
| Notes/files metadata | SQLite plus local registered files |
| Retrieval chunks + FTS5 index | SQLite (`retrieval_chunks` + `retrieval_chunks_fts`) |
| Agent trace metadata | SQLite (`agent_traces`, `agent_trace_steps`) |
| LLM calls | JSONL/SQLite audit logs |
| Tool/action events | JSONL audit logs |

SQLite is the v1 operational source of truth for persisted Atenas rows. A
Markdown/YAML source-of-truth workflow is post-v1 unless the reconciliation
protocol in `docs/DATA_MODEL.md` is implemented.

Do not maintain duplicate schema definitions for the same table. Schema changes
belong in one canonical migration/schema owner.

## Configuration

Configuration is loaded in the application shell and passed down. Avoid hidden
imports from `core/` into `app.config`.

Required startup validation:

- If Telegram is enabled, `TELEGRAM_ALLOWED_USER_IDS` must be non-empty.
- Dashboard/API bind host must default to `127.0.0.1`.
- External LLM provider settings must be explicit opt-in.

## Current Implementation State

Implemented:

1. Telegram plain messages use the bounded `AgentLoop` and `ToolRegistry`.
2. The tool registry exposes read, compute, act, system, and opt-in web tools
   with Pydantic argument/result schemas and declared action tiers.
3. The action-tier gate auto-runs reversible local writes, holds
   confirm-first actions, denies forbidden or unknown actions through policy,
   and audit-logs action outcomes.
4. Duplicate detection, delete/deduplicate modules, `archive_note`,
   `update_memory`, and opt-in `web_search` are present as agent tools.
5. Dashboard/API are local-only by default; Telegram allowlist startup failure
   is loud when Telegram is enabled.
6. Retrieval indexing uses incremental sync into SQLite/FTS5 with lexical
   fallback.
7. `NLRouter` and `NLClassifier` are quarantined as legacy compatibility
   surfaces; new NL product work belongs in `AgentLoop` and `ToolRegistry`.
8. FR-06 planning acceptance coverage exists for hard-block collision,
   availability bounds, fatigue caps, deadline coverage, determinism, and
   heavy-week capacity reduction.
9. Work-shift `fatigue_level` is accepted through the shared service,
   Telegram `/add_shift`, and the `add_work_shift` agent tool.
10. Slash-command and agent-tool parity is audited in
    `docs/COMMAND_TOOL_PARITY.md`.

Remaining v1 architecture work:

1. Add release/deployment checks for local bind and Compose publishing.
