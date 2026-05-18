# Telegram Bot

## Purpose

Telegram interface for all write operations and quick read queries. Commands are allowlist-protected.

## Files

| File | Role |
|------|------|
| `app/bot.py` | All command handlers, allowlist filter, application builder |

## Command categories

### Read commands (no data modification)
- `/ping` — health check
- `/status` — skill status output
- `/skills` — available skills
- `/today` — today's schedule
- `/week` — weekly overview
- `/deadlines` — upcoming assignments
- `/availability` — today's study windows
- `/plan` — study plan
- `/study` — next study recommendation
- `/modules` — list modules
- `/classes` — list class sessions
- `/shifts` — list work shifts
- `/assignments` — list open assignments
- `/notes` — list recent notes
- `/note <id>` — view single note
- `/files` — list registered files
- `/search <query>` — search notes and files
- `/ask_notes q="..."` — answer from registered notes/files with sources
- `/ask_note note=12 q="..."` — answer from one non-archived note only
- `/sources q="..."` — list retrieval sources without generating an answer

### Write commands (allowlist-protected)
- `/add_module` — create study module
- `/add_class` — create class session
- `/add_shift` — create work shift
- `/add_assignment` — create assignment
- `/set_status` — update assignment status
- `/set_hours` — update completed hours
- `/add_note` — create study note
- `/archive_note` — archive a note
- `/add_file` — register file metadata
- `/link_note_file` — link note to file

## Key functions

- `build_application()` — constructs the PTB application with all handlers.
- `AllowlistFilter` — blocks updates from non-allowed user IDs.
- `parse_kv_args()` (in `validators.py`) — parses `key="value"` and `key=value` pairs.
- `_build_retrieval_service()` — builds the local controlled retrieval service.
- `_format_retrieval_answer()` — formats source-grounded answers and Ollama-unavailable fallbacks.

## Important constraints

- All commands go through `AllowlistFilter`.
- Write commands use the same filter as read commands.
- `parse_kv_args` supports quoted values with spaces: `title="My Note"`.
- Handlers use `_get_bot_settings(context)` to get settings from `bot_data`.
- Retrieval commands accept optional `module`, `assignment`, and `limit` filters.
- `/ask_notes` and `/ask_note` call local Ollama only after sources are found.
- `/sources` never calls the LLM; it only returns source labels and snippets.
- If no sources are found, retrieval commands return the no-source fallback.

## Pitfalls

- Do not remove allowlist filter from write commands.
- Command handlers expect `update.effective_message.text`; guard against None.
- `_reply()` silently returns if no effective message exists.
- Date parsing is strict; work shifts require time component.
- Do not add cloud fallback or web search to retrieval commands.
- `/ask_note` scopes to note chunks only and passes `include_files=False`.

## Related tests

- `tests/test_bot.py` — allowlist and basic commands
- `tests/test_data_commands.py` — data management commands
- `tests/test_schedule_commands.py` — scheduling commands
- `tests/test_planning_commands.py` — planning commands
- `tests/test_retrieval_commands.py` — retrieval commands
