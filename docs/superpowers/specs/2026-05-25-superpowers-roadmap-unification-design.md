# Superpowers Roadmap Unification Design

## Purpose

Unify the Superpowers docs into one live roadmap so future Atenas work has a
clear phase order. The repository already contains archival implementation
plans, current specs, and partially completed hardening phases. Readers need a
single place that explains what is shipped, what is partial, what comes next,
and which large-file refactors should support the next implementation phases.

## Current State

- `docs/README.md` is the canonical project docs index.
- `docs/superpowers/specs/2026-05-24-atenas-v1-gap-and-packaging-spec.md`
  records the v1 gap closure state.
- `docs/superpowers/plans/*.md` are historical plans and already contain
  archival notices guarded by `tests/test_docs_status.py`.
- Durable runtime state exists in `core/nl/runtime_state.py` and is wired into
  Telegram confirmation for plain `yes` and `no` replies.
- `/pending` and `/cancel_pending` are specified but not registered Telegram
  commands.
- Toolsets exist in `core/nl/toolsets.py` and are wired into the agent loop.
- Backup and restore exist in `core/backup.py` and `app/cli.py`.
- Model profiles, prompt assembly, trace replay/search, approved skill memory,
  and the channel adapter boundary are not implemented.
- The largest implementation files are `app/bot.py`, `core/nl/tools.py`,
  `core/nl/router.py`, and the academic service/import/repository cluster.

## Design

Create `docs/superpowers/README.md` as the live Superpowers roadmap. It will not
replace canonical product docs; it will organize implementation phases derived
from the current Superpowers specs and the verified code state.

The roadmap will include:

1. A "How to read this folder" section that distinguishes live roadmap, current
   specs, and archival plans.
2. A phase table with statuses:
   - Done: v1 gap/package closure, durable pending-action storage base,
     toolsets, backup/restore.
   - Partial: pending-action UX, because durable yes/no works but deterministic
     `/pending` and `/cancel_pending` commands are missing.
   - Next: local model profile config, budgeted prompt assembly and tighter tool
     selection, trace replay/search.
   - Later: approved skill memory and channel adapter boundary.
3. A refactor-support section that records the big files to split before or
   during future work:
   - Split `app/bot.py` into Telegram application wiring, NL confirmation flow,
     academic commands, knowledge/retrieval commands, LLM note commands,
     notification jobs, and shared formatting.
   - Split `core/nl/tools.py` into registry mechanics, tool definitions,
     academic handlers, knowledge/retrieval handlers, memory handlers, web
     handlers, and action execution helpers.
   - Keep `core/nl/router.py` and `core/nl/classifier.py` quarantined as legacy
     compatibility until tests and imports can be migrated to the tool loop.
4. A "Cut candidates" section that avoids deleting history but names what should
   not grow:
   - Historical Superpowers plans stay archival.
   - No new product behavior should land in `NLRouter` or `NLClassifier`.
   - Generated local state, dependency caches, `.env`, SQLite files, and logs
     remain ignored runtime data.

Update `docs/README.md` to point implementation readers to the Superpowers
roadmap after the canonical docs list. If the roadmap exposes stale canonical
implementation-state wording, update that wording to match the verified code
without changing the product contract.

Extend `tests/test_docs_status.py` with guardrails that:

- `docs/superpowers/README.md` exists.
- It identifies itself as the live roadmap.
- It names all archival plan files as archival records.
- It names the partial pending-action UX gap so completed and remaining runtime
  state work are not conflated.

## Out Of Scope

- Do not delete historical Superpowers specs or plans in this slice.
- Do not refactor implementation files in the roadmap slice.
- Do not implement `/pending`, model profiles, prompt assembly, trace replay, or
  skill memory in this slice.
- Do not change the canonical agent loop, product, security, or requirements
  contracts except for pointers to the new roadmap and narrow implementation
  snapshot corrections that prevent contradiction with verified code.

## Testing

Run:

```bash
.venv/bin/pytest tests/test_docs_status.py -q
.venv/bin/pytest -q
```

Expected result: the documentation guardrail test passes, and the full suite
continues to pass without requiring a live local LLM.

## Implementation Order

1. Add failing roadmap guardrails to `tests/test_docs_status.py`.
2. Add `docs/superpowers/README.md`.
3. Update `docs/README.md` to link to the live roadmap.
4. Run focused docs tests.
5. Run the full test suite.
