# Atenas Superpowers Roadmap

## Status

This is the live roadmap for Superpowers-driven Atenas work. Canonical product
contracts still live in `docs/README.md` and the canonical docs listed there.
This file only answers: which Superpowers specs and phases are current, which
plans are archival, what comes next, and which refactors support that work.

## How To Read This Folder

- `docs/superpowers/README.md` is the live roadmap.
- `docs/superpowers/specs/*.md` are design records. Some remain current, but
  implementation status is summarized here.
- `docs/superpowers/plans/*.md` are archival implementation records. Their
  unchecked boxes preserve original task breakdowns, not current project state.

Archival plans:

- `docs/superpowers/plans/2026-05-21-atenas-audit-hardening.md`
- `docs/superpowers/plans/2026-05-21-atenas-tui.md`
- `docs/superpowers/plans/2026-05-24-hermes-inspired-agent-hardening.md`
- `docs/superpowers/plans/2026-05-24-local-model-agent-runtime-state.md`
- `docs/superpowers/plans/2026-05-25-superpowers-roadmap-unification.md`

## Phase Status

| Phase | Status | Source | Current note |
|---|---|---|---|
| v1 gap and packaging closure | Done | `docs/superpowers/specs/2026-05-24-atenas-v1-gap-and-packaging-spec.md` | Package discovery, planning acceptance, parity audit, doc drift cleanup, and v1 tool coverage are implemented and tested. |
| Durable pending-action storage base | Done | `docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md` | `core/nl/runtime_state.py` persists threads and pending actions; Telegram `yes` and `no` can resolve durable pending actions. |
| Pending-action UX | Done | `docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md` | Durable confirmation exists, and deterministic `/pending` plus `/cancel_pending` commands are registered. |
| Toolsets | Done | `docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md` | `core/nl/toolsets.py` groups safe, egress, destructive, readonly, and dev-local tools; the agent loop filters visible tools by selected toolsets. |
| Backup and restore | Done | `docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md` | `core/backup.py` and `atenas backup`/`atenas restore` exist with tests. |
| v1 defect and governance closure | Done | `docs/superpowers/specs/2026-06-12-v1-defect-and-governance-closure-spec.md` | All WP1–WP6 fixes landed 2026-06-13: tool crashes, policy/audit governance on add_* tools, X-Forwarded-For guard, pending-action status, /confirm command, command audit logging, dead-module removal, SQLite connection hygiene, WAL-safe backup, Portuguese toolset markers. |
| Local model profile config | Next (current priority) | Runtime state and Hermes specs | Add explicit context length, timeout, prompt limits, and doctor output. |
| Budgeted prompt assembly and tighter tool selection | Next | Runtime state spec | Extract prompt assembly from `core/nl/agent.py`, enforce model-profile budgets, and record selection metadata. |
| Trace replay and search | Next | Runtime state and Hermes specs | Extend trace inspection without rerunning writes or exposing full prompts by default. |
| Approved skill memory | Later | Hermes spec | Store reviewed procedural memories as context only; never grant permissions. |
| Channel adapter boundary | Later | Hermes spec | Extract only when a second channel is actually scoped. |

## Refactor Support

Large files should be split as they are touched by the next phases:

- `app/bot.py`: split into Telegram application wiring, NL confirmation flow,
  academic commands, knowledge/retrieval commands, LLM note commands,
  notification jobs, and shared formatting.
- `core/nl/tools.py`: split into registry mechanics, tool definitions,
  academic handlers, knowledge/retrieval handlers, memory handlers, web
  handlers, and action execution helpers.
- `core/nl/router.py` and `core/nl/classifier.py`: keep quarantined as legacy
  compatibility until tests and public imports are migrated to the tool loop.
- `core/academic/service.py`, `core/academic/importers.py`, and
  `core/academic/repository.py`: split only when adding or changing academic
  behavior, so repository/service boundaries stay clear.

## Cut Candidates

- Do not add new product behavior to `NLRouter` or `NLClassifier`; they are
  legacy compatibility surfaces.
- Do not create new live checklist docs under `docs/superpowers/plans/`.
  Historical plans remain archival records.
- Keep generated local state, dependency caches, `.env`, SQLite files, logs,
  inbox contents, and output artifacts ignored as runtime data.
- Do not delete historical specs or plans just to reduce file count; preserve
  them as records and point readers to this roadmap for current state.

## Next Recommended Slice

Implement local model profile config (explicit context length, timeout, prompt
limits, and doctor output) before prompt-budget and trace replay work. The v1
defect and governance closure spec is complete as of 2026-06-13.
