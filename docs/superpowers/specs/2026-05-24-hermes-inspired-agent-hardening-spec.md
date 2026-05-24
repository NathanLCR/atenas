# Hermes-Inspired Agent Hardening Spec

## Purpose

This spec captures the parts of Hermes Agent that are worth borrowing for
Atenas without changing Atenas into a general autonomous agent framework.

Hermes is useful as architecture reference because it is local/self-hostable,
model-provider flexible, toolset-oriented, persistent across sessions, and
organized around memory plus reusable skills. Atenas should borrow those
patterns only where they strengthen the Telegram-first study assistant.

This spec builds on:

- `docs/AGENT_LOOP.md`
- `docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md`
- `docs/superpowers/specs/2026-05-24-atenas-v1-gap-and-packaging-spec.md`

## Research Signals

Hermes patterns that matter for Atenas:

- **Learning loop:** Hermes describes a closed loop that persists knowledge and
  skills across sessions.
- **Memory vs skills:** Hermes separates facts from procedures. Memories are
  things the agent knows; skills are reusable ways to do tasks.
- **Toolsets:** Hermes organizes tools into logical sets that can be enabled or
  disabled by platform.
- **Local model config:** Hermes treats local/custom OpenAI-compatible endpoints
  as first-class, including model name, provider, base URL, context length, and
  local-model timeout behavior.
- **Session search:** Hermes exposes persistent session and memory recall.
- **Backup/export:** Hermes documents moving state between machines with a
  backup workflow.
- **Messaging gateway:** Hermes supports many messaging platforms, but the
  useful pattern for Atenas is the adapter boundary, not the platform sprawl.

Sources:

- Hermes FAQ: https://hermes-ai.net/en/docs/faq/
- Hermes tools and toolsets: https://hermes-agent.nousresearch.com/docs/user-guide/features/tools/
- Hermes FAQ and local model configuration: https://hermes-agent.nousresearch.com/docs/reference/faq
- Hugging Face Hermes Agent integration overview: https://huggingface.co/docs/inference-providers/en/integrations/hermes-agent

## Design Decision

Borrow the following ideas:

1. Toolsets per surface and risk profile.
2. Approved skill memory for reusable study/planning procedures.
3. Backup and restore for the SQLite source of truth.
4. Local model profile configuration with explicit context length and timeout.
5. Searchable session and trace recall.
6. A future channel adapter boundary.

Do not borrow:

- broad terminal/file/browser tool access
- multi-agent delegation
- autonomous RL training tools
- remote tool gateways by default
- unapproved skill creation
- multi-platform write surfaces in v1

## Component 1: Toolsets

### Goal

Make the tool catalog easier for weak local models and safer for every product
surface by grouping tools into named, deterministic toolsets.

### Proposed Toolsets

| Toolset | Surface | Tools | Rule |
|---|---|---|---|
| `telegram-safe` | Telegram | status, schedule, assignments, notes, retrieval, reversible local writes | Enabled by default for allowlisted Telegram users |
| `telegram-egress` | Telegram | web search, export, external provider calls | Disabled by default; confirm-first |
| `telegram-destructive` | Telegram | delete, deduplicate, archive, clear | Available only when explicitly requested; confirm-first |
| `tui-readonly` | TUI | dashboard/status/schedule/notes/retrieval reads | Read-only |
| `dashboard-readonly` | Web dashboard | read-only dashboard queries | Read-only |
| `dev-local` | CLI | doctor, traces, replay, packaging checks | Local developer use only |

### Implementation Shape

Add `core/nl/toolsets.py`:

- `ToolsetName`
- `ToolsetPolicy`
- `ToolsetRegistry`
- `tools_for_surface(surface, enabled_flags) -> list[str]`

`ToolRegistry` remains the owner of tool definitions. Toolsets only filter and
group existing tools.

### Acceptance Criteria

- Every `ToolDefinition` belongs to at least one toolset.
- Telegram prompt assembly uses only tools allowed by the selected Telegram
  toolsets.
- TUI and dashboard toolsets contain no act tools.
- Egress/destructive toolsets are never enabled silently.
- Tests prove `web_search` is absent unless `telegram-egress` and
  `enable_web_tools` are both active.

## Component 2: Approved Skill Memory

### Goal

Create a safe version of Hermes-style self-improvement. Atenas can notice a
repeated successful workflow and propose a reusable skill, but it cannot install
or execute an unapproved skill.

### Skill Types

| Type | Example | Execution |
|---|---|---|
| `planning_playbook` | How to plan a heavy work week | Used as retrieval context for planning |
| `study_protocol` | How to revise a lecture note | Used as tool guidance/context |
| `dissertation_routine` | How to prepare for supervision | Used as checklist/context |
| `operational_runbook` | How to debug Ollama unavailable | CLI/dev guidance only |

### Lifecycle

```text
trace evidence
  -> proposed skill draft
  -> user reviews
  -> approved skill stored in SQLite
  -> skill retrieved as context on similar tasks
  -> skill can be archived or revised
```

### Safety Rules

- Skills are Markdown/procedure text, not executable code.
- The LLM may propose a skill draft, but code stores it as `pending`.
- User approval is required before a skill becomes active.
- Active skills may guide answers and tool choice, but never bypass policy.
- Skills may not grant filesystem, shell, egress, or destructive authority.

### SQLite Tables

```sql
CREATE TABLE IF NOT EXISTS agent_skills (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    source_trace_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_skills_status
ON agent_skills(status, kind);
```

### Acceptance Criteria

- A skill can be proposed, approved, listed, retrieved, and archived.
- Pending skills are never injected into the agent prompt as active guidance.
- Active skills are included only as delimited context.
- Skill body content is treated as untrusted data, not instructions that can
  change tool policy.

## Component 3: Backup And Restore

### Goal

Protect the v1 SQLite source of truth before Atenas relies on more persistent
agent state.

### Commands

- `atenas backup`
- `atenas restore PATH`
- `atenas backup --include-logs`
- `atenas backup --manifest-only`

### Backup Contents

Default backup includes:

- `data/atenas.sqlite`
- `memory/` files
- `inbox/` manifest with paths, hashes, and sizes
- approved skill records
- runtime state tables
- backup manifest JSON

Default backup excludes:

- `.env`
- API keys and Telegram tokens
- dependency caches
- full logs unless `--include-logs` is passed
- generated output unless explicitly requested in a later spec

### Acceptance Criteria

- Backup creates a timestamped archive under `output/backups/`.
- Manifest records version, created time, included paths, hashes, and excluded
  secret paths.
- Restore refuses to overwrite an existing DB unless `--force` is passed.
- Restore validates the manifest before writing.
- Tests use temporary directories and never read the real local `.env`.

## Component 4: Local Model Profile Config

### Goal

Make local model behavior explicit rather than hidden in scattered settings.

### Settings

Add:

- `ollama_context_length`
- `ollama_stream_timeout_seconds`
- `agent_max_prompt_chars`
- `agent_max_tools_per_prompt`
- `agent_model_profile`

### Behavior

- `atenas doctor` reports configured model, base URL, context length, timeout,
  and model availability.
- Agent prompt assembly reads the model profile.
- If context length is below the recommended floor for agent mode, doctor
  prints a warning.
- Local-model timeout errors are reported distinctly from invalid JSON and tool
  validation failures.

### Acceptance Criteria

- Settings parse from environment variables.
- Doctor output shows model profile details.
- Tests cover default values and custom environment overrides.

## Component 5: Session Search And Trace Recall

### Goal

Let Nathan ask why Atenas did something and let developers debug local-model
behavior without reading raw logs.

### Features

- `atenas traces --query "duplicate modules"`
- `atenas replay-trace TRACE_ID`
- Telegram read tool: `search_agent_history`
- Dashboard read-only trace search

### Safety Rules

- Search trace summaries and tool metadata by default.
- Do not expose full prompts, note bodies, file bodies, or secrets.
- Search results can inform an answer, but cannot authorize actions.

### Acceptance Criteria

- Agent traces can be searched by user summary, final summary, tool name, and
  status.
- `search_agent_history` is read-only.
- Trace replay prints deterministic metadata and never reruns writes.

## Component 6: Channel Adapter Boundary

### Goal

Prepare for future channels without making v1 multi-platform.

### Interfaces

```text
Actor
Channel
InboundMessage
OutboundMessage
ConfirmationAdapter
```

Telegram remains the only v1 write channel. The boundary exists to keep future
Discord/email/CLI experiments from leaking into core policy logic.

### Acceptance Criteria

- Telegram actor ID remains the source of confirmation authority.
- Core agent runtime receives channel-neutral actor/message objects.
- No new remote write channel is enabled.

## Recommended Order

1. Finish durable pending actions from the local-model runtime-state spec.
2. Implement toolsets.
3. Implement backup/restore.
4. Implement local model profile config.
5. Implement approved skill memory.
6. Implement session search and trace recall.
7. Extract channel adapter boundary only when a second channel is actually
   being built.

Toolsets and backups are the best first Hermes-inspired slices because they
reduce risk immediately without increasing agent autonomy.
