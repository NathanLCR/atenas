# Changelog

All notable changes to Atenas are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **WP1 — Reliable tool-decision parsing**: the decision call now passes
  `format="json"` to the Ollama client (backends that ignore the field degrade
  gracefully). On a parse/validation failure the loop makes exactly one bounded
  repair re-ask with the validation error and required JSON shape; the repair
  does not count against `max_tool_calls`. Only after repair fails does the loop
  use the existing safe fallback. Repair attempts are recorded in the agent trace
  (`repair_count` column on `agent_traces`).

## [0.1.0] - 2026-06-16

First deliverable release: Atenas runs from a clean clone and can be handed to
another person.

### Added

- Telegram-first interface: deterministic slash commands plus a plain-message
  LLM tool-calling agent loop with read, compute, auto-tier, and confirm-first
  tools.
- Action-tier governance: reversible local writes run and are audit-logged;
  destructive and egress actions require explicit confirmation; forbidden
  actions are blocked.
- Academic scheduling and deterministic study planning, including fatigue-aware
  availability and FR-06 acceptance coverage.
- Notes, files, and retrieval over SQLite with FTS5 and a lexical fallback.
- Local FastAPI API and read-only dashboard, bound to `127.0.0.1` behind a
  local-only guard.
- Read-only terminal UI (`atenas tui`).
- `atenas` CLI with `doctor`, `traces`, `tui`, `backup`, and `restore`.
- Local Ollama as the default LLM provider; cloud providers are opt-in and
  disabled by default.
- `docs/GETTING_STARTED.md` onboarding guide, `CONTRIBUTING.md`, and an MIT
  `LICENSE`.
- GitHub Actions CI running the test suite on Python 3.11.

### Fixed

- Runtime directories (`data`, `logs`, `memory`, `inbox`, `output`) are now
  created automatically on app startup and by `atenas doctor`, so a fresh
  clone runs and the full test suite passes without manual setup.

[Unreleased]: https://github.com/nathanlcr/atenas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nathanlcr/atenas/releases/tag/v0.1.0
