# Atenas Slash Command And Agent Tool Parity

Verified on 2026-05-25.

This audit records whether each supported Telegram slash command has an
equivalent v1 agent tool. Command-only entries are intentional v1 support
surfaces, not missing tool coverage. Shared command/tool behavior must continue
to route through core services for validation, policy, persistence, and audit
behavior.

| Slash command | Agent path | Status |
|---|---|---|
| `/ping` | Command-only | Local adapter health shortcut; `get_status` covers agent status. |
| `/status` | `get_status` | Equivalent read path. |
| `/skills` | Command-only | Telegram command catalog/help surface. |
| `/pending` | Command-only | Deterministic pending-action review shortcut backed by `AgentRuntimeStore`. |
| `/cancel_pending` | Command-only | Deterministic pending-action cancellation shortcut backed by `AgentRuntimeStore`. |
| `/today` | `get_today_overview` | Equivalent read path. |
| `/week` | `get_week_overview` | Equivalent read path. |
| `/deadlines` | `get_deadlines` | Equivalent read path. |
| `/availability` | `get_availability` | Equivalent read path. |
| `/plan` | `generate_study_plan` | Equivalent compute path. |
| `/study` | `suggest_next_task` | Equivalent compute path. |
| `/add_module` | Command-only | Module creation remains a deterministic v1 shortcut; agent module writes are post-v1. |
| `/add_class` | `add_class_session` | Shared `AcademicService.add_class_session` path. |
| `/add_shift` | `add_work_shift` | Shared `AcademicService.add_work_shift` path, including `fatigue_level`. |
| `/add_assignment` | `add_assignment` | Shared `AcademicService.add_assignment` path. |
| `/set_status` | `set_assignment_status` | Shared update service path. |
| `/set_hours` | `set_assignment_hours` | Shared update service path. |
| `/modules` | `list_modules` | Equivalent read path. |
| `/classes` | `list_class_sessions` | Equivalent read path. |
| `/shifts` | `list_work_shifts` | Equivalent read path. |
| `/assignments` | `list_assignments` | Equivalent read path. |
| `/reminders` | Command-only | Telegram notification review shortcut; no v1 agent reminder tool. |
| `/add_note` | `add_note` | Shared `KnowledgeService.create_note` path. |
| `/notes` | `search_notes` | Equivalent search path. |
| `/note` | `search_notes` | Agent uses search by note title/content instead of numeric command lookup. |
| `/archive_note` | `archive_note` | Confirm-first path through `ToolRegistry.execute_pending`. |
| `/add_file` | Command-only | Local filesystem support command; unrestricted file paths are not exposed to the agent. |
| `/files` | Command-only | Registered-file listing is a support shortcut; retrieval uses `retrieve_sources`. |
| `/search` | `search_notes` | Equivalent local search path. |
| `/link_note_file` | Command-only | Manual file linking waits for a separate confirmed file-tool contract. |
| `/ask_notes` | `retrieve_sources` | Equivalent retrieval path. |
| `/ask_note` | `retrieve_sources` | Equivalent retrieval path scoped by query/context. |
| `/sources` | `retrieve_sources` | Equivalent retrieval source path. |
| `/summarize_note` | `retrieve_sources` | Agent uses retrieval grounding; command keeps deterministic LLM note helper. |
| `/explain_note` | `retrieve_sources` | Agent uses retrieval grounding; command keeps deterministic LLM note helper. |
| `/questions_note` | `retrieve_sources` | Agent uses retrieval grounding; command keeps deterministic LLM note helper. |
| `/flashcards_note` | `retrieve_sources` | Agent uses retrieval grounding; command keeps deterministic LLM note helper. |
| `/rewrite_note` | `retrieve_sources` | Agent uses retrieval grounding; command keeps deterministic LLM note helper. |

Regression coverage:

- `tests/test_command_tool_parity.py` requires every catalog command to have an
  explicit parity entry.
- Tool-backed entries must name a registered `ToolRegistry` tool.
- Command-only entries must include a rationale.
