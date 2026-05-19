# Atenas Handoff — Telegram LLM Tool Interface

## Date

2026-05-19

## Status

Spec rewrite only. This replaces the earlier "thin natural-language command
router" handoff. The new direction is Telegram-first LLM agent with Atenas
tools.

Implementation is not claimed complete by this document. Use this as the next
implementation contract.

## Product Identity

Name: Atenas
Repo: `study-agent-cd`
Language: Python 3.11
Stack: FastAPI, python-telegram-bot, SQLite, local Ollama-compatible LLM

Atenas is a local-running, Telegram-first personal study assistant. The app,
database, files, dashboard, and REST API stay local. Telegram is the main user
interface. The LLM should answer naturally and call controlled tools for
Atenas functionality.

## What Changed

The previous NL spec treated natural language as a classifier that mapped text
to existing slash-command handlers. That is no longer the intended product.

New target:

```text
Telegram message
  -> allowlist auth
  -> LLM agent
  -> Atenas tool registry
  -> core services
  -> structured result
  -> Telegram response
```

Slash commands stay. They are shortcuts, not the only interface.

## Security Posture

- Local-only dashboard/API.
- Telegram allowlist is mandatory.
- Empty Telegram allowlist is a startup error when Telegram is enabled.
- Local Ollama is the default LLM provider.
- External LLM provider use is explicit opt-in and must be treated as data egress.
- Write tools require confirmation and policy approval.

## Current Telegram Surface to Preserve

Status:

- `/ping`
- `/status`
- `/skills`
- `/reminders`

Schedule/planning:

- `/today`
- `/week`
- `/deadlines`
- `/availability`
- `/plan`
- `/study`

Controlled data input/editing:

- `/add_module`
- `/add_class`
- `/add_shift`
- `/add_assignment`
- `/set_status`
- `/set_hours`
- `/modules`
- `/classes`
- `/shifts`
- `/assignments`

Knowledge:

- `/add_note`
- `/notes`
- `/note`
- `/archive_note`
- `/add_file`
- `/files`
- `/search`
- `/link_note_file`

Selected-note local LLM:

- `/summarize_note`
- `/explain_note`
- `/questions_note`
- `/flashcards_note`
- `/rewrite_note`

Retrieval:

- `/ask_notes`
- `/ask_note`
- `/sources`

Do not remove or change command behavior while adding the tool-agent path.

## Target Tool Layer

The tool layer should be explicit and small. It may start inside an existing
module, but the responsibilities must be clear.

Tool definition fields:

- `name`
- `description`
- `tool_class`: `read`, `planning`, `write`, or `system`
- argument schema
- result schema
- handler function
- required policy action for writes

The LLM sees tool schemas. It does not see service objects, repositories,
database connections, filesystem paths, or shell access.

## Initial Tool Set

### Read tools

- `get_status`
- `get_today_overview`
- `get_week_overview`
- `get_deadlines`
- `get_availability`
- `list_modules`
- `list_assignments`
- `list_notes`
- `search_notes`
- `retrieve_sources`

### Planning tools

- `generate_study_plan`
- `suggest_next_task`
- `explain_deadline_risk`

### Write proposal tools

- `add_assignment`
- `set_assignment_status`
- `set_assignment_hours`
- `add_note`
- `archive_note`
- `add_class_session`
- `add_work_shift`

### System tools

- `get_local_llm_status`
- `get_app_health`
- `get_safe_config_summary`

## Read Example

```text
User: What should I work on today?

LLM tool calls:
- get_today_overview()
- list_assignments(status="active")
- suggest_next_task()

Telegram reply:
Concise recommendation with the next task, deadline context, and any capacity warning.
```

## Write Example

```text
User: Mark my ML essay as done

LLM tool calls:
- list_assignments(query="ML essay")
- set_assignment_status(id="assignment_uuid", status="done") as proposal

Bot:
Confirm status change?
Assignment: ML Essay
New status: done
Reply "yes" to confirm or "no" to cancel.

User: yes

Execution:
- policy check
- service update
- audit log
- Telegram result
```

## Required Write Flow

Every write must follow this sequence:

1. Authenticate Telegram user by allowlist.
2. Validate tool arguments.
3. Resolve titles/modules/labels to stable IDs.
4. Create pending proposal in per-user conversation state.
5. Show a Telegram confirmation summary.
6. On `yes`, run policy check.
7. Execute through core service.
8. Log action and policy outcome.
9. Return structured result to the LLM and user.

Do not call a router/service write method directly from the LLM confirmation
path.

## Prompt and Tool Safety

- Delimit user messages in prompts.
- Delimit retrieved notes/files in prompts.
- Tell the model source text is data, not instructions.
- Tool calls must satisfy schema validation.
- Retrieved content must never grant tool permissions.
- Full prompt/response logging is off by default.

## Architecture Boundaries

- `app/` wires Telegram, FastAPI, config, and dependencies.
- `core/` owns services, policy, data, retrieval, and LLM clients.
- `core/` must not import `app.config`; settings are injected.
- Tool handlers call services; they do not duplicate Telegram formatting.
- Telegram formatting should be shared where slash commands and agent replies
  need the same content.

## Implementation Notes

The existing `core/nl/` classifier/router work may be reused only if it moves
toward the tool-agent contract:

- Intent classification alone is not the final architecture.
- Natural-language writes must not bypass policy.
- Title/module lookup must resolve to IDs before execution.
- Tests must use real `Settings` test objects or isolated fixtures, not
  `MagicMock` settings that fall back to local `.env`.

## Tests Required

- Telegram allowlist rejects unauthorized users before LLM/tool calls.
- Empty allowlist fails startup when Telegram is enabled.
- Plain Telegram message can call read tools and produce a response.
- LLM write proposal asks for confirmation and does not mutate before `yes`.
- Confirmation `yes` runs policy before service execution.
- Confirmation `no` cancels without side effects.
- Title-to-ID resolution works for assignment status changes.
- Prompt templates delimit untrusted text.
- LLM provider is mocked; tests do not call real Ollama/cloud providers.
- Tests use isolated temp databases/config.

## Definition of Done

The Telegram LLM tool interface is complete when:

1. A plain Telegram message can answer status/schedule/planning questions by
   calling tools.
2. A plain Telegram message can ask about notes/files and receive sourced retrieval output.
3. A plain Telegram write request produces a confirmation prompt before mutation.
4. Confirmed writes pass policy and audit logging.
5. Slash commands still work.
6. Dashboard/API remain local-only support surfaces.
7. Tests pass in an isolated environment.

## Docs to Read First

1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/SECURITY.md`
4. `docs/AGENT_POLICY.md`
5. `docs/REQUIREMENTS.md`
6. `docs/code-map/telegram.md`
7. `docs/code-map/core-knowledge.md`
