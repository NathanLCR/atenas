# Atenas — Handoff Package

## What's in this folder

Core spec docs are in `docs/`, with newer phase/code-map handoff material in
subdirectories:

```
docs/
├── HANDOFF.md                 ← Current verified state and next-phase handoff
├── CODEX_BUILD_PROMPT.md      ← Original Phase 1 build prompt
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
├── study_planner.md           ← Study planner skill spec — legacy Phase 8
├── phases/                    ← Current phase-by-phase roadmap
├── codex/                     ← Codex handoff and next-phase prompts
└── code-map/                  ← Developer architecture map
```

## How to use

The current implementation is beyond the original Phase 1 skeleton. To work
with it:

1. Read `HANDOFF.md`.
2. Read `codex/MASTER_CODEX_HANDOFF.md`.
3. Read the active next phase spec in `phases/`.
4. Create or refresh a Python 3.11 environment.
5. `pip install -r requirements.txt`
6. Run `pytest` - all tests must pass before and after changes.
7. Run `docker-compose up` or `uvicorn app.main:app --reload`.

For future phases, prefer the newer `docs/phases/`, `docs/codex/`, and
`docs/code-map/` docs over the original Phase 1 prompt.

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
