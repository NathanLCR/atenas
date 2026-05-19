# Atenas — Requirements

## Status

Target requirements as of 2026-05-19. These requirements supersede older
phase-order assumptions where they conflict.

## Functional Requirements

### FR-01 — Telegram-First Interface

- System MUST accept Telegram slash commands.
- System MUST accept plain Telegram messages through the LLM tool agent.
- System MUST enforce `TELEGRAM_ALLOWED_USER_IDS` before commands, LLM calls,
  retrieval, or tools run.
- System MUST fail startup when Telegram is enabled with an empty allowlist.
- System MUST respond with compact, readable Telegram output.
- System MUST preserve slash commands as deterministic shortcuts.

### FR-02 — Local Dashboard and REST API

- System MUST expose dashboard/API surfaces only as local support tools.
- Dashboard/API MUST bind to `127.0.0.1` by default.
- Docker Compose publishing MUST bind to localhost only.
- Dashboard MUST be read-only unless a later authenticated write spec is
  approved.
- REST endpoints MUST NOT use fake authentication such as `user_id=0` for
  privileged behavior.

### FR-03 — LLM Tool Agent

- System MUST provide the LLM with explicit Atenas tools.
- Tools MUST have validated argument schemas and structured result schemas.
- Tools MUST call application/core services; the LLM MUST NOT access services,
  repositories, files, or shell commands directly.
- Tools MUST be classified as read, planning, write, or system.
- Read tools MAY execute after Telegram allowlist validation.
- Write tools MUST create pending action proposals instead of mutating directly.

### FR-04 — Write Confirmation and Policy

- System MUST require explicit Telegram confirmation before LLM-initiated writes.
- System MUST resolve natural-language titles/modules to stable IDs before write execution.
- System MUST validate all write proposals before policy evaluation.
- System MUST pass every write through the policy engine before execution.
- System MUST log policy decisions and action outcomes.
- System MUST report failed writes clearly and MUST NOT silently drop them.

### FR-05 — Academic Scheduling

- System MUST accept modules, class sessions, work shifts, assignments, and deadlines.
- Work shifts and class sessions MUST be treated as hard planning blocks.
- Fatigue level MUST affect planning intensity.
- System MUST list and update assignment status and estimated hours.

### FR-06 — Study Planning

- System MUST generate daily and weekly study plans from available blocks,
  active assignments, deadlines, class sessions, work shifts, and fatigue.
- Plans MUST respect hard blocks and fatigue caps.
- Deterministic code MUST author time slots and enforce collision checks.
- The LLM MAY choose or explain tasks inside code-authored slots, but MUST NOT
  invent arbitrary times.
- Plans MUST surface warnings when demand exceeds capacity.

### FR-07 — Notes, Files, and Retrieval

- System MUST store notes and registered files locally.
- System MUST search notes/files.
- System MUST retrieve sources from registered, non-archived content.
- Retrieval answers MUST include source labels or a no-source fallback.
- Querying retrieval MUST NOT rebuild the full chunks table every time.
- `retrieval_chunks` schema MUST have one canonical owner.

### FR-08 — LLM Study Assistance

- System MUST support LLM help over selected local context, such as summarize,
  explain, questions, flashcards, rewrite, and note/file Q&A.
- Prompt templates MUST delimit untrusted user/source text.
- Retrieved content MUST never grant tool permissions.
- LLM unavailable states MUST degrade gracefully without breaking slash commands.

### FR-09 — LLM Provider Policy

- Local Ollama MUST be the default provider.
- External LLM providers MUST be disabled by default.
- Enabling an external provider MUST be explicit and documented as data egress.
- Sensitive content MUST NOT be sent to external providers without explicit
  per-use consent.

### FR-10 — Logging

- System MUST log commands, LLM calls, tool calls, policy decisions, and action outcomes.
- Logs MUST include timestamp, actor, tool/command, provider/model where
  relevant, outcome, and a short payload summary.
- Logs MUST NOT include secrets.
- Full prompt/response logging MUST be disabled by default.

### FR-11 — Architecture Boundaries

- Dependencies MUST flow from `app/` to `core/`, not from `core/` to `app/`.
- Settings/config MUST be injected into core services instead of imported from
  `app.config`.
- Dead placeholder modules MUST be implemented, documented as intentionally
  reserved, or removed.
- Fake LLM telemetry MUST NOT be written as real LLM calls.

## Non-Functional Requirements

### NFR-01 — Local-Running

- Core app data MUST remain local.
- The app MUST work without public dashboard/API exposure.
- Telegram and optional external LLM providers are the only expected remote
  transports.

### NFR-02 — Reliability

- System MUST use transactions for multi-step writes.
- System MUST not silently lose writes.
- System MUST produce clear user-facing errors for blocked or failed actions.

### NFR-03 — Performance

- Deterministic read commands SHOULD complete in under 2 seconds.
- Local LLM commands SHOULD acknowledge quickly and enforce timeouts.
- Retrieval queries SHOULD avoid full reindexing on every request.
- Slow LLM/provider failures MUST not block unrelated slash commands.

### NFR-04 — Testability

- Core services, tool schemas, policy checks, and confirmation flows MUST have tests.
- Tests MUST mock LLM providers and MUST NOT require a real model.
- Tests MUST avoid reading real local `.env` or production database state.
- The full suite MUST be runnable with `pytest`.

### NFR-05 — Inspectability

- SQLite schema MUST be documented.
- Logs MUST be readable with a text editor or `jq`.
- Tool/action audit trails MUST be sufficient to reconstruct what changed.

### NFR-06 — Portability

- System SHOULD run on macOS and Linux.
- System SHOULD run in Docker Compose for local development.
- Docker images MUST NOT include generated tool junk or local secrets.

## Out of Scope for v1

- Multi-user SaaS operation.
- Public web deployment.
- Unauthenticated LAN access.
- Autonomous shell execution.
- Self-modifying code.
- Browser automation as a product feature.
- Calendar/email integrations unless separately scoped.
