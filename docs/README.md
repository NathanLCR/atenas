# Atenas — Handoff Package

## What's in this folder

```
CODEX_BUILD_PROMPT.md          ← Give this to Claude Code for Phase 1
docs/
├── PRODUCT_SPEC.md            ← What Atenas is
├── REQUIREMENTS.md            ← FRs and NFRs
├── ARCHITECTURE.md            ← Component map, decisions
├── AGENT_POLICY.md            ← LLM routing, planning rules, safety
├── SECURITY.md                ← Forbidden actions, prompt injection
├── DATA_MODEL.md              ← SQLite schema (corrected), entities
├── SCHEMAS.md                 ← LLM output schemas (corrected)
├── ROADMAP.md                 ← Build phases
└── skills/
    ├── status.md              ← Phase 1 — implement this
    ├── memory.md              ← Phase 4
    ├── work_schedule.md       ← Phase 5
    └── study_planner.md       ← Phase 6
```

## How to use

1. Create a new repo called `atenas-core`.
2. Copy `docs/` into the repo root.
3. Give Claude Code the contents of `CODEX_BUILD_PROMPT.md` as the task.
4. Review the output against the acceptance criteria at the bottom of the prompt.
5. Run `pytest` — all tests must pass.
6. Run `docker-compose up` — healthcheck must pass.

## What was corrected

The PDF spec (`atenas_framework_spec.pdf`) and the generated spec pack had conflicts.
All conflicts were resolved before generating these docs:

| Conflict | Resolution |
|---|---|
| PK types (INTEGER vs TEXT) | TEXT UUIDs — matches PDF |
| fatigue_level (int 1-5 vs text enum) | TEXT: low/medium/high — matches PDF |
| Work shift schema (single vs array) | Array wrapper + needs_confirmation — matches PDF |
| Memory schema (minimal vs structured) | should_store + domain + importance — matches PDF |
| Plan schema (missing fields) | capacity + reason + warnings — matches PDF |
| Confidence threshold (0.5/0.6/0.65) | 0.65 everywhere — matches PDF |
| work_shifts missing date column | Added separate date column — improvement over PDF |
