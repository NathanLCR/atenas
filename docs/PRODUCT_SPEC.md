# Atenas — Product Specification

## Product Name
Atenas

## Repository
`study-agent-cd`

## Status
Target product contract as of 2026-05-19. This document describes the intended
local-running, Telegram-first system. If implementation differs, the code is
behind the spec.

---

## One-Line Description
A Telegram-first, local-running LLM study assistant for working students.

## Core Product Statement
Atenas helps students who also work manage classes, work shifts, assignments,
deadlines, notes, files, retrieval, and study plans. The primary interaction is
Telegram. The LLM can answer naturally and call controlled Atenas tools, while
code owns validation, policy, scheduling math, and persistence.

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
| Telegram agent | Plain Telegram messages are handled by an allowlisted LLM agent with Atenas tools |
| Slash commands | Stable command shortcuts for status, schedule, planning, notes, files, retrieval, and writes |
| Memory/notes | Store and search notes, facts, preferences, module info |
| Work schedule | Ingest work shifts; use them to constrain planning |
| Class timetable | Ingest class schedule; treat as fixed blocks |
| Assignment tracking | Track assignments, deadlines, task estimates |
| Study planning | Generate realistic daily and weekly study plans |
| Retrieval | Answer questions over registered notes/files with explicit sources |
| LLM study help | Summarise, explain, draft questions, rewrite, and generate flashcards from selected local context |
| Controlled writes | Add or update academic data only after confirmation and policy checks |

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
4. **LLM decides meaning. Tools execute capabilities. Code controls actions.**
5. **Tool calls are structured.** The LLM never imports repositories or calls services directly.
6. **Read and write are different trust levels.** Reads may run after allowlist auth; writes require confirmation and policy.
7. **All tool arguments and LLM outputs are validated before acting.**
8. **Memory and logs must be human-inspectable.**
9. **No unrestricted autonomous shell execution.**
10. **Build small, safe, and debuggable.**

## LLM Provider Policy

Local Ollama is the default provider for the Telegram agent and study
features. External LLM providers are optional, disabled by default, and must be
called out clearly because Telegram prompt content, retrieved context, and tool
results may leave the machine.

---

## Success Criteria for v1

Atenas v1 is complete when it can:

1. Receive and respond to plain Telegram messages through an allowlisted LLM agent.
2. Preserve slash commands as deterministic shortcuts.
3. Let the LLM call read tools for status, schedule, planning, notes, files, and retrieval.
4. Let the LLM propose write tools for assignments, notes, schedule data, and statuses.
5. Execute write tools only after confirmation and policy approval.
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
