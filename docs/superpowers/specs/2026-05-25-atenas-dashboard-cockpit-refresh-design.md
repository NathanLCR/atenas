# Atenas Dashboard Cockpit Refresh Design

## Goal

Refresh the local read-only Atenas dashboard with the supplied cockpit design while preserving the existing FastAPI and Jinja structure. The dashboard remains a secondary local support surface for inspection, not a replacement for Telegram-first workflows.

## Inputs

- Design zip: `/Users/nathanlucio/Downloads/stitch_atenas_local_study_cockpit.zip`
- Source design notes: `stitch_atenas_local_study_cockpit/atenas_terminal/DESIGN.md`
- Designed screens reviewed: Overview, Week, Study Plan, Retrieval Diagnostics, Agent Traces, and mobile Overview
- Existing implementation: `app/dashboard.py`, `app/templates/*.html`, `app/static/styles.css`, and dashboard tests under `tests/`

## Product Constraints

- Keep the dashboard local-only and read-only.
- Do not add real Add Event, Regenerate, Clear, Export, Adjust Constraints, or other mutating controls.
- Query, filter, navigation, and read-only inspection are allowed.
- Do not add Tailwind CDN, Material Symbols CDN, or any external runtime dependency from the mockups.
- Preserve Telegram as the primary Atenas interface. Dashboard/API are local support surfaces.
- Keep edits scoped to dashboard routes, dashboard templates, CSS, focused helper functions, and tests.

## Shell And Visual System

The dashboard will use one shared cockpit shell across all pages:

- 240px fixed desktop sidebar with Atenas brand, Study Orchestrator subtitle, grouped navigation, and active route state.
- Compact 48px topbar with the current page title, a rectangular `Local-Only` indicator, and small read-only status glyphs rendered with CSS/text rather than external icon fonts.
- Bottom local status strip with retrieval and agent status text.
- Main content offset by the sidebar on desktop, with stacked content and horizontal nav on mobile.
- Flat bordered panels only. No shadows, gradients, or floating marketing sections.
- Dense operational spacing based on 4px units.
- Mono labels for status, metadata, IDs, timings, query text, and log-like output.
- Rectangular chips with 2-6px radii. No pills.

Palette follows the zip's Atenas Terminal direction:

- Background and surfaces: off-white workspace, white panels, pale blue sidebar.
- Active state: blue left border or blue chip.
- Semantic states: green success/healthy, amber warnings/fatigue medium, red danger/high fatigue or failures.
- Borders: low-contrast blue-grey outlines.

## Page Treatment

### Overview

Overview gets the richest local cockpit summary:

- Today's Summary panel from real `get_today_overview()` data.
- Next Study Block panel from the deterministic plan's next future block.
- Upcoming Deadlines panel from real upcoming assignments.
- System Health panel from local read-only signals such as retrieval source count, latest trace status, and LLM call status.
- Weekly Capacity panel from real week availability summaries, showing work, classes, and study minutes as horizontal bars.

Empty states must be honest: no fabricated study block, deadline, or health metric. When data is unavailable, panels say there is no local data yet and point back to Telegram commands only as text.

### Week

Week becomes a timeline-style schedule from real `overview.availability.days` data:

- Header uses the actual Monday-Sunday date range.
- Columns represent each day.
- Rows use the local availability calculation's day window, with reasonable CSS placement from event start/end times.
- Blocked class/work windows and free study windows are both shown.
- Study windows are dashed and green-accented.
- Work/class windows use solid flat fills and semantic left borders.
- Fatigue and max-intensity chips render when present in metadata or study windows.

No Add Event or week navigation controls are added because they imply writes or missing route behavior.

### Plan

Plan becomes a deterministic block table:

- Summary strip for available, required, planned, and unscheduled minutes.
- Table rows for real `StudyPlan.blocks`.
- Columns: Time, Assignment, Intensity, Reasoning, Status.
- Intensity chips come from `PlannedStudyBlock.intensity`.
- Status is scheduled for blocks, warning for unscheduled workload, and danger for overdue or unestimated workload warnings.
- Warning rows keep current warning coverage for unscheduled, unestimated, and overdue assignments.

No Regenerate or Adjust Constraints buttons are added.

### Retrieval

Retrieval becomes a diagnostic read-only query surface:

- Keep the existing GET query form and filters.
- Show compact diagnostic panels for query state, source count, and model/unavailable state.
- Show answer panel only after a query.
- Show source rows with mono citation labels, source kind, title, and snippets.
- If the local LLM is unavailable but sources exist, show the existing `ollama serve` hint as read-only terminal text.
- Preserve module and assignment filters exactly.

### Traces

Traces becomes an execution table plus stdout-style summary panel:

- Execution table uses existing `agent_traces` records.
- Columns: Timestamp, Status, User, Model, Tools, Pending, Message.
- Right-side stdout panel is generated from the newest trace records, not from fake static examples.
- Empty state remains explicit.

No Clear or Export CSV controls are added.

### Secondary Pages

Deadlines, Data, Notes, Files, Search, LLM, and Logs inherit the new shell, panels, chips, table styling, forms, and empty states. They do not receive major new behavior.

## Route And Helper Design

`app/dashboard.py` may add small read-only helpers:

- `_dashboard_globals(request, title, section)` for common shell context.
- `_build_overview_context(settings)` for today's overview, next study block, upcoming deadlines, workload, health, and capacity.
- `_build_week_timeline(overview)` for CSS placement metadata derived from real blocked/study windows.
- `_build_trace_summary(records)` for stdout-style trace lines from real trace rows.
- Formatting helpers for dates, compact minutes, percentages, intensity/status labels, and timeline offsets.

Helpers must not mutate the database. They may call existing read-only services and read SQLite log tables.

## Testing

Add focused tests before implementation for changed helper/context behavior:

- Home route renders real today/next block/deadline/capacity context and local-only shell markers.
- Week route renders timeline schedule classes for blocked and study windows while preserving existing schedule content.
- Plan route renders deterministic block table columns and intensity/status/warning data while preserving existing empty states.
- Retrieval route preserves query/filter behavior and renders diagnostic answer/source/unavailable states.
- Traces route renders execution table plus real stdout-style trace summary and preserves empty state.
- Shell contains no mutating dashboard controls such as Add Event, Regenerate, Clear, Export CSV, or Adjust Constraints.

Run targeted dashboard tests first, then broader `pytest` if feasible.

## Non-Goals

- No dashboard writes.
- No external assets or runtime dependencies.
- No authentication or remote deployment changes.
- No redesign of Telegram, core planning, retrieval, LLM services, or database schema.
- No fabricated telemetry values presented as real.
