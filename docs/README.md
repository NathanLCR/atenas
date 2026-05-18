# Atenas — Handoff Package

## What's in this folder

All spec docs are flat inside `docs/`:

```
docs/
├── CODEX_BUILD_PROMPT.md      ← Phase 1 build prompt for Claude Code
├── PRODUCT_SPEC.md            ← What Atenas is
├── REQUIREMENTS.md            ← FRs and NFRs
├── ARCHITECTURE.md            ← Component map, decisions
├── AGENT_POLICY.md            ← LLM routing, planning rules, safety
├── SECURITY.md                ← Forbidden actions, prompt injection
├── DATA_MODEL.md              ← SQLite schema (corrected), entities
├── SCHEMAS.md                 ← LLM output schemas (corrected)
├── ROADMAP.md                 ← Build phases
├── status.md                  ← Status skill spec — Phase 1
├── memory.md                  ← Memory skill spec — Phase 4
├── work_schedule.md           ← Work schedule skill spec — Phase 5
├── class_timetable.md         ← Class timetable skill spec — Phase 6
└── study_planner.md           ← Study planner skill spec — Phase 8
```

## How to use

Phase 1 is already implemented in this repo. To work with it:

1. `pip install -r requirements.txt`
2. Run `pytest` — all tests must pass.
3. Run `docker-compose up` (or `uvicorn app.main:app --reload`) and hit `GET /health`.

For later phases, use `docs/CODEX_BUILD_PROMPT.md` as the pattern and follow `ROADMAP.md`. These docs are the source of truth; keep them in sync with the code.

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
