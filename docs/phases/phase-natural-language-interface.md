# Phase: Telegram LLM Tool Interface

## Status

Next implementation target. Supersedes the older thin natural-language
classifier/router phase.

## Goal

Allow Nathan to use Atenas primarily by talking to the Telegram bot. The LLM
should understand the request, call controlled Atenas tools, and reply in
Telegram.

The user should be able to write:

```text
what should I work on today?
mark my ML essay as done
how many study hours do I have this week?
summarise note 3
what do my notes say about attention mechanisms?
add assignment: NLP Essay due Friday at 5pm, priority high
```

## Product Question

```text
Can I use Atenas from Telegram without memorising commands?
```

## In Scope

- Plain Telegram message handler.
- Allowlist validation before LLM/tool execution.
- LLM agent with Atenas tool schemas.
- Read tools for status, schedule, planning, notes, files, and retrieval.
- Write proposal tools for assignments, notes, shifts, classes, and statuses.
- Per-user pending confirmation state for writes.
- Policy engine execution after confirmation.
- Slash commands preserved unchanged.
- Local Ollama as default provider.
- Mocked LLM/tool tests.

## Out of Scope

- Replacing slash commands.
- Public dashboard/API exposure.
- Web search.
- Autonomous shell/filesystem access.
- External LLM providers unless explicitly enabled by a separate config/spec.
- Multi-user behavior.
- Writes without confirmation.

## Architecture

```text
Telegram text message
  -> allowlist check
  -> LLM agent
  -> tool registry
  -> core service
  -> structured tool result
  -> LLM response
  -> Telegram reply
```

Write path:

```text
Telegram text message
  -> allowlist check
  -> LLM proposes write tool
  -> validate args and resolve stable IDs
  -> pending confirmation
  -> user replies yes/no
  -> policy engine
  -> service execution
  -> audit log
  -> Telegram result
```

## Design Rules

1. The LLM receives tool schemas, not service objects.
2. Tools call existing services and do not duplicate business logic.
3. Read tools may run after allowlist auth.
4. Write tools create proposals; they do not mutate directly.
5. Confirmation is set by code after the user replies `yes`.
6. Policy runs before every confirmed write.
7. Natural-language labels are resolved to stable IDs before writes.
8. Prompt templates delimit user text and retrieved source text.

## Initial Tools

| Tool | Class | Purpose |
|---|---|---|
| `get_status` | read | App/student status |
| `get_today_overview` | read | Today's schedule and study context |
| `get_week_overview` | read | Weekly schedule overview |
| `get_deadlines` | read | Upcoming deadlines |
| `get_availability` | read | Available study time |
| `list_assignments` | read | Assignment lookup/listing |
| `list_modules` | read | Module lookup/listing |
| `search_notes` | read | Keyword note/file search |
| `retrieve_sources` | read | Source retrieval for note/file Q&A |
| `generate_study_plan` | planning | Daily/weekly plan generation |
| `suggest_next_task` | planning | Next best study action |
| `add_assignment` | write | Create assignment proposal |
| `set_assignment_status` | write | Status-change proposal |
| `set_assignment_hours` | write | Estimated-hours proposal |
| `add_note` | write | Note creation proposal |
| `archive_note` | write | Note archive proposal |
| `add_class_session` | write | Class-session proposal |
| `add_work_shift` | write | Work-shift proposal |

## Conversation Examples

### Read

```text
User: what's my plan today?
Agent tools: get_today_overview, suggest_next_task
Bot: You have 2 useful study blocks today...
```

### Retrieval

```text
User: what do my notes say about CNNs?
Agent tools: retrieve_sources(query="CNNs")
Bot: Your notes mostly frame CNNs as... Sources: note:5, file:2
```

### Write

```text
User: mark ML essay done
Agent tools: list_assignments(query="ML essay"), set_assignment_status(...)
Bot: Confirm status change? Assignment: ML Essay. New status: done.
User: yes
Bot: Updated ML Essay to done.
```

## Tests

Use mocked LLM responses and isolated app settings.

Required coverage:

- Unauthorized Telegram user does not trigger LLM/tools.
- Empty allowlist startup validation.
- Plain message invokes read tools.
- Retrieval path returns source labels or no-source fallback.
- Write proposal does not mutate before confirmation.
- `yes` executes only after policy approval.
- `no` cancels pending write.
- Assignment title resolution maps to stable ID.
- Prompt templates delimit untrusted input.
- LLM unavailable path degrades without breaking slash commands.

## Exit Criteria

The phase is complete when:

1. Plain Telegram messages can read status/schedule/planning data through tools.
2. Plain Telegram messages can answer note/file questions with sources.
3. Plain Telegram write requests require confirmation and policy.
4. Slash commands still pass their tests.
5. No test depends on a real local database, `.env`, or live LLM.
