# Changelog

All notable changes to Atenas are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Demo mode**: `atenas demo` seeds a synthetic study week (fictional modules,
  recurring classes, work shifts incl. a late high-fatigue close, assignments due
  relative to today, three notes) through the core services so the dashboard and
  planner can be explored without Telegram or Ollama. Refuses on a database that
  already has modules unless `--force`; `--db PATH` targets another database.
- **`TRUSTED_CLIENT_NETWORKS`**: narrow allowlist of private/loopback CIDRs the
  local-only guard accepts (still subject to the `X-Forwarded-For` check).
  Invalid, public, and any-address CIDRs are rejected at config load.
- **`DASHBOARD_STAMP_LINE1` / `DASHBOARD_STAMP_LINE2`** replace the hardcoded
  school stamp in the dashboard header.

- **WP1 — Reliable tool-decision parsing**: the decision call now passes
  `format="json"` to the Ollama client (backends that ignore the field degrade
  gracefully). On a parse/validation failure the loop makes exactly one bounded
  repair re-ask with the validation error and required JSON shape; the repair
  does not count against `max_tool_calls`. Only after repair fails does the loop
  use the existing safe fallback. Repair attempts are recorded in the agent trace
  (`repair_count` column on `agent_traces`).

- **WP2 — Tool result curation and pagination**: all read/compute list tools
  (`list_modules`, `list_assignments`, `list_class_sessions`, `list_work_shifts`,
  `search_notes`, `retrieve_sources`, `detect_duplicate_modules`) now support
  `limit` (default 10), `offset` (default 0), and `verbosity` (`"concise"` or
  `"detailed"`, default `"concise"`). Concise mode returns only actionable
  summary fields; detailed mode returns the full object. Results include
  `total` and `truncated` in `data`, and the message signals pagination
  (e.g., "Showing 1–10 of 23. Use offset=10 to see more."). Invalid
  pagination arguments return a steering error, not a crash.

### Changed

- **Docker quickstart now works**: compose uses a fixed-subnet network and trusts
  only its gateway, reaches host Ollama via `host.docker.internal`, adds an
  optional `ollama` profile, and the image installs the `atenas` CLI and has a
  `/health` healthcheck. `.dockerignore` also excludes `.env.*`, SQLite files, tests.
- Default `TIMEZONE` is now `UTC`, matching `.env.example` (set `TIMEZONE`
  explicitly to keep a local zone such as `Europe/Dublin`).
- Dashboard truthfulness: next focus names its day when it is not today, classes
  show per-class times instead of a min-max span, the header reads "free to
  study", and the Study Plan card shows planned minutes (it previously showed
  work + classes + free study time labelled "committed"). Unused reads removed.

### Fixed

- Comma-separated `TELEGRAM_ALLOWED_USER_IDS` and `KNOWLEDGE_FILE_ROOTS` in the
  environment (as in `.env.example`) no longer crash settings load.

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
