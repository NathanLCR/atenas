# Phase 0 — Spec Foundation

## Status

Complete.

## Goal

Define Atenas before building it.

Atenas is a local-first AI study operating system for working students. It manages:

- classes
- work shifts
- assignments
- deadlines
- study plans
- notes
- files
- memory
- future local/cloud LLM assistance

## Core product question

```text
What should I study today or this week, considering my classes, work shifts, deadlines, notes, and energy?
```

## Main decisions

- Build first for Nathan, but keep architecture ready for future students.
- Local-first.
- Telegram as primary interface.
- Simple web dashboard.
- SQLite + local files for v1.
- Local LLM for small/private tasks later.
- Cloud fallback only after deterministic/local foundation is stable.
- Spec-driven development.
- Atenas is separate from Hermes or other agents.

## Non-goals

Do not start with:

- RAG
- autonomous agents
- cloud LLM orchestration
- production multi-user auth
- complex UI
- full calendar sync
- overengineered architecture

## Deliverables

- product definition
- requirements
- architecture direction
- roadmap
- safety/policy constraints
- phase structure

## Exit criteria

Phase 0 is complete when the project has a clear scope, architecture direction, and implementation sequence.
