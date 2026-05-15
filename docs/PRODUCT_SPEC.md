# Atenas — Product Specification v0.1

## Product Name
Atenas

## Repository
atenas-core

## Version
0.1 — Foundation

---

## One-Line Description
A local-first AI study operating system for working students.

## Core Product Statement
Atenas helps students who also work manage classes, work shifts, assignments, deadlines, PDFs, notes, and study plans — and creates realistic study schedules around their actual available time.

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
- A local AI system that runs without depending on cloud subscriptions for daily use.
- A human-inspectable memory system — no black-box state.

## What Atenas Is Not

- A generic study chatbot.
- A learning management system.
- An autonomous agent with shell access.
- A multi-user SaaS product (v1).
- A replacement for human judgement on high-stakes decisions.

---

## Core Capabilities (v1)

| Capability | Description |
|---|---|
| Memory | Store and search notes, facts, preferences, module info |
| Work schedule | Ingest work shifts; use them to constrain planning |
| Class timetable | Ingest class schedule; treat as fixed blocks |
| Assignment tracking | Track assignments, deadlines, task estimates |
| Study planning | Generate realistic daily and weekly study plans |
| PDF ingestion | Upload and summarise academic papers |
| Semantic search | Search notes and papers by meaning |
| Literature matrix | Extract structured metadata from papers |
| Flashcards | Generate simple revision flashcards |

---

## Interface

**Primary:** Telegram bot (`/commands`)
**Secondary:** Simple web dashboard (FastAPI + Jinja + HTMX)

The dashboard is for review and editing, not primary interaction.

---

## Design Principles

1. **Spec before code.** No feature is implemented without a written spec.
2. **Files are source of truth.** Human-readable Markdown/YAML files are the canonical state.
3. **SQLite stores metadata and state.** Not the other way around.
4. **LLM decides meaning. Code controls structure and actions.**
5. **Local LLM handles cheap tasks. Cloud handles complex tasks.**
6. **All LLM output must be schema-validated before acting on it.**
7. **Dangerous actions require explicit confirmation.**
8. **Memory must be human-inspectable at all times.**
9. **No unrestricted autonomous shell execution.**
10. **Build small, safe, and debuggable.**

---

## Success Criteria for v1

Atenas v1 is complete when it can:

1. Receive and respond to Telegram commands.
2. Display a simple readable web dashboard.
3. Store memory safely and consistently.
4. Search memory semantically.
5. Accept a class timetable.
6. Accept work shifts with fatigue and commute context.
7. Accept assignments and deadlines.
8. Generate a realistic daily study plan.
9. Generate a realistic weekly study plan.
10. Respect work shifts and fatigue in all planning.
11. Upload, chunk, and summarise academic PDFs.
12. Search notes and PDFs semantically.
13. Use local LLM for routine tasks.
14. Use cloud LLM only for complex reasoning.
15. Log every action with timestamp and source.
16. Block unsafe or forbidden actions.
17. Remain fully inspectable and debuggable by Nathan.
