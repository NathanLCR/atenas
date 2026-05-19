# Atenas — Architecture

## Status

Target architecture as of 2026-05-19. This is the contract the code should be
refactored toward. It does not claim every path is already implemented.

## Guiding Principle

> The LLM decides meaning. Tools expose capabilities. Code controls actions.

The LLM is never trusted to execute application logic directly. It receives a
small set of structured tools. Tool arguments are validated, write proposals
are confirmed by the user, the policy engine runs before mutation, and services
own the actual business logic.

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
LLM agent with Atenas tools                Existing command handlers
    |
    v
Tool registry
    |
    +-- read tools ------------------------------+
    |                                            |
    +-- write proposal tools                     |
         |
         v
    Confirmation manager
         |
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
SQLite / local files / JSONL logs
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
- LLM client/service abstractions.
- Policy engine and action execution.
- Database schema and repository access.

Core services receive configuration and dependencies through constructors or
method parameters. They do not import `app.config`.

### `tools/` or equivalent tool layer

The LLM-facing tool layer is the bridge between conversation and capabilities.
It should be thin and explicit:

- Defines tool names, descriptions, argument schemas, and result schemas.
- Calls existing services; it does not duplicate service behavior.
- Marks tools as read or write.
- Produces write proposals instead of mutating directly.
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
| Read tools | status, today, week, deadlines, modules, assignments, notes, files, retrieval sources | May run after Telegram allowlist auth |
| Planning tools | generate plan, suggest next task, explain deadline risk | May run after auth; must use deterministic service inputs |
| Write tools | add assignment, set status, add note, add class, add shift, archive note | Must create a pending proposal, require confirmation, pass policy |
| System tools | local LLM status, app health, configuration summary | Read-only; never reveal secrets |

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

```text
User: "mark my ML essay done"
  -> allowlist check
  -> LLM calls find_assignment(title="ML essay")
  -> LLM proposes set_assignment_status(id="...", status="done")
  -> bot asks for confirmation
  -> user replies "yes"
  -> policy engine validates the action
  -> service executes the update
  -> audit log records outcome
```

Writes must never execute directly from the LLM response. Confirmation text is
not enough by itself; execution must pass through a policy-checked path.

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
| Retrieval chunks | SQLite, single canonical schema |
| LLM calls | JSONL/SQLite audit logs |
| Tool/action events | JSONL audit logs |

Do not maintain duplicate schema definitions for the same table. Schema changes
belong in one canonical migration/schema owner.

## Configuration

Configuration is loaded in the application shell and passed down. Avoid hidden
imports from `core/` into `app.config`.

Required startup validation:

- If Telegram is enabled, `TELEGRAM_ALLOWED_USER_IDS` must be non-empty.
- Dashboard/API bind host must default to `127.0.0.1`.
- External LLM provider settings must be explicit opt-in.

## Implementation Priorities

1. Lock the local-only transport posture.
2. Make Telegram allowlist failure loud at startup.
3. Introduce the LLM tool registry and shared read/write tool contracts.
4. Route all writes through confirmation and policy.
5. Remove or quarantine dead modules and fake LLM telemetry.
6. Fix retrieval indexing so queries do not rebuild everything.
7. Push dependency direction to `app -> core`, never `core -> app`.
