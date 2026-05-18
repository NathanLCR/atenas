# Phase 6.5 — Developer Code Map

## Status

Complete.

The code map exists in `docs/code-map/` and should be kept in sync with future
phase work.

## Goal

Create lightweight developer documentation so future coding agents and humans can understand Atenas without loading excessive context.

## Why this matters

Atenas is growing. Future agents need concise architectural maps instead of reading every file.

This reduces:

- context usage
- duplicated explanations
- accidental refactors
- stale assumptions
- onboarding friction

## In scope

Create:

```text
docs/code-map/
  README.md
  architecture-map.md
  core-academic.md
  core-knowledge.md
  telegram.md
  dashboard.md
  database-schema.md
```

If `core/knowledge` is not implemented yet, skip `core-knowledge.md` until Phase 6 is complete.

## Documentation style

Do not document every function mechanically.

Each file should include:

- package/module purpose
- main files
- main classes/functions
- important data flow
- important constraints
- related tests
- common pitfalls

## Code comments/docstrings

Add docstrings only to public functions/classes where behavior is non-obvious.

Add comments only for tricky logic or edge cases.

Do not add verbose comments to obvious code.

## Out of scope

Do not:

- change runtime behavior
- rewrite architecture
- add new dependencies
- duplicate all source code in docs
- create massive generated documentation

## Tests

Run:

```bash
python3 -m pytest
```

## Exit criteria

Phase 6.5 is complete when concise code-map docs exist and tests still pass.
