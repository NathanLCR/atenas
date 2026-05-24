# Atenas — Product Specification

## Product Name
Atenas

## Repository
`study-agent-cd`

## Status
Target product contract as of 2026-05-20, with implementation status refreshed
on 2026-05-24. This document describes the intended local-running,
Telegram-first v1 system. If implementation differs, the code is behind the
spec unless the difference is explicitly recorded as a current v1 gap below.

---

## One-Line Description
A Telegram-first, local-running LLM study assistant for working students.

## Core Product Statement
Atenas helps students who also work manage classes, work shifts, assignments,
deadlines, notes, files, retrieval, and study plans. The primary interaction is
Telegram. The LLM can answer naturally and call controlled Atenas tools, while
code owns validation, policy, scheduling math, and persistence.

## Operating Doctrine

```text
The LLM is an agent with strong tools.
Deterministic systems validate and do the heavy lifting.
The human approves only what deletes or leaves the machine.
Everything that changes is logged.
```

Atenas is a **tool-calling agent**, not a fixed intent menu. The local model is
weak at reasoning, so it is given strong, validated tools (read, compute, act)
and a loop in which it calls a tool, observes the result, and decides the next
step — carrying the user's goal across turns. Deterministic code owns schemas,
ID resolution, policy, scheduling math, and persistence. The full contract for
the loop and the action tiers lives in `docs/AGENT_LOOP.md`.

Governance is **tiered**, not all-or-nothing:

- **Auto** — reversible, local, low-risk writes (add/update a note, set a
  status, add a class or shift) execute directly and are logged.
- **Confirm-first** — destructive actions (delete, clear, bulk-remove) and
  egress (external messages, exports, sensitive data to an external LLM) require
  explicit human confirmation before execution.
- **Forbidden** — shell, source edits, secret reads, unrestricted filesystem are
  blocked unconditionally.

Web access is opt-in and treated with care: a query is egress, and returned
content is untrusted data, never instructions.

## Primary Question Atenas Answers
> What should I study today or this week, given my classes, work shifts, deadlines, notes, and energy?

---

## Target User

**Primary:** Nathan — MSc student with part-time/full-time hospitality work.

**Generalised target (future):**
- MSc students
- International students with irregular schedules
- Students with part-time or shift-based work
- Dissertation students managing multiple deadlines
- Students with limited, fragmented study time

---

## What Atenas Is

- A planning and memory operating layer for students with constrained time.
- A system that understands work shifts as first-class scheduling constraints.
- A local-running assistant that does not require a public web service.
- A Telegram-first LLM agent with tools for Atenas functions.
- A human-inspectable memory system — no black-box state.

## What Atenas Is Not

- A generic study chatbot.
- A learning management system.
- An autonomous agent with shell access.
- A multi-user SaaS product (v1).
- A remotely exposed dashboard/API product.
- A replacement for human judgement on high-stakes decisions.

---

## Core Capabilities (v1)

| Capability | Description |
|---|---|
| Telegram agent | Plain Telegram messages are handled by an allowlisted LLM tool-calling agent that loops over Atenas tools |
| Slash commands | Stable command shortcuts for status, schedule, planning, notes, files, retrieval, and writes |
| Memory/notes | Store and search notes, facts, preferences, module info |
| Work schedule | Ingest work shifts; use them to constrain planning |
| Class timetable | Ingest class schedule; treat as fixed blocks |
| Assignment tracking | Track assignments, deadlines, task estimates |
| Study planning | Generate realistic daily and weekly study plans |
| Retrieval | Answer questions over registered notes/files with explicit sources |
| LLM study help | Summarise, explain, draft questions, rewrite, and generate flashcards from selected local context |
| Governed writes | The agent acts directly on reversible local writes; destructive and egress actions require confirmation; every change is validated, policy-checked, and audit-logged |

## Current Implementation Snapshot

Verified on 2026-05-24:

- Telegram slash commands cover core status, schedule/planning, academic data,
  notes/files, retrieval, LLM note helpers, reminders, and confirmation
  replies.
- Plain Telegram messages use the canonical bounded `AgentLoop` and
  `ToolRegistry`, not the legacy fixed-intent router.
- `ToolRegistry` currently exposes v1 read, compute, act, system, and opt-in
  web tools for the main product areas listed above.
- Confirm-first destructive/egress tools create pending Telegram confirmations;
  auto-tier local writes execute through policy and audit logging.
- The local dashboard and TUI exist as read-only support surfaces.
- Retrieval uses registered, non-archived notes/files, incremental SQLite/FTS5
  indexing, and local Ollama for generated answers when available.
- Editable install package discovery is configured so only `app*`, `core*`, and
  `skills*` are importable packages.

Remaining v1 gaps:

- Planning has deterministic availability and slot allocation, but the full
  falsifiable FR-06 acceptance suite is not yet complete.
- Work shifts store `fatigue_level`, but common Telegram/agent write paths
  still expose `energy_cost` rather than a complete fatigue-level input.
- Slash-command and agent-tool parity still needs a final audit so shared
  validation, policy, and audit behavior are consistent everywhere.

---

## Interface

**Primary:** Telegram bot.

Telegram supports:

- Plain messages routed to the LLM tool agent.
- Slash commands as fast deterministic shortcuts.
- Confirmation replies (`yes` / `no`) for pending write proposals.

**Secondary:** local FastAPI API and read-only web dashboard.

The dashboard and REST API are local support surfaces. They must bind to
localhost by default and are not safe to expose directly on a LAN or public
host.

---

## Design Principles

1. **Spec before code.** No feature is implemented without a written spec.
2. **Telegram first.** Optimize the product around the Telegram experience.
3. **Local-running by default.** SQLite, files, dashboard, and API stay local.
4. **The LLM is a tool-calling agent.** It loops over validated tools and carries the goal across turns; it does not map messages to a fixed intent menu.
5. **Tool calls are structured.** The LLM never imports repositories or calls services directly.
6. **Governance is tiered.** Reads and reversible local writes run directly; destructive and egress actions require confirmation; forbidden actions are blocked. See `docs/AGENT_LOOP.md`.
7. **Everything that changes is logged.** Agency is traded for an audit trail, not for prior approval on every action.
8. **All tool arguments and LLM outputs are validated before acting.**
9. **Memory and logs must be human-inspectable.**
10. **No unrestricted autonomous shell execution; web access is opt-in and guarded.**
11. **Build small, safe, and debuggable.**

## LLM Provider Policy

Local Ollama is the default provider for the Telegram agent and study
features. External LLM providers are optional, disabled by default, and must be
called out clearly because Telegram prompt content, retrieved context, and tool
results may leave the machine.

---

## Success Criteria for v1

Atenas v1 is complete when it can:

1. Receive and respond to plain Telegram messages through an allowlisted LLM tool-calling agent that loops over tools and carries the goal across turns.
2. Preserve slash commands as deterministic shortcuts.
3. Let the agent call read and compute tools for status, schedule, planning, notes, files, retrieval, and cross-referencing (e.g. duplicate detection).
4. Let the agent act on reversible local writes directly (assignments, notes, schedule data, statuses), with validation and an audit-logged outcome.
5. Require explicit human confirmation before destructive (delete, clear, bulk) or egress (external message, export, sensitive external-LLM) actions, then validate, policy-check, execute, and log.
6. Display a simple local read-only dashboard.
7. Store memory safely and consistently.
8. Search memory by keyword and retrieve over registered notes/files.
9. Accept a class timetable.
10. Accept work shifts with fatigue and commute context.
11. Accept assignments and deadlines.
12. Generate a realistic daily study plan.
13. Generate a realistic weekly study plan.
14. Respect work shifts and fatigue in all planning.
15. Answer questions over registered notes/files with explicit sources.
16. Use local LLM by default for routine tasks.
17. Log every command, tool call, LLM call, policy decision, and action result.
18. Block unsafe or forbidden actions.
19. Remain fully inspectable and debuggable by Nathan.
