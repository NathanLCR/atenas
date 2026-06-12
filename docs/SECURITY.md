# Atenas — Security Policy

## Status

Target security contract as of 2026-05-20. This document describes required
behavior. If implementation differs, the implementation is non-compliant until
fixed.

## Security Posture

Atenas is a single-user, local-running assistant.

- The dashboard and REST API are local support surfaces.
- They must bind to `127.0.0.1` by default.
- Docker/Compose publishing must bind to localhost only.
- Direct LAN/public exposure is out of scope and unsafe unless a later spec
  adds authentication, authorization, TLS, and deployment hardening.
- Telegram is the primary interface and is remote by nature, so Telegram
  allowlist enforcement is mandatory.
- Local Ollama is the default LLM provider. External LLM providers and web
  access are opt-in data egress.
- Security follows the project doctrine: the LLM is a tool-calling agent;
  deterministic code validates and gates by action tier; the human approves only
  destructive and egress actions; every change is audit-logged. The full
  behavior contract is `docs/AGENT_LOOP.md`.

## Threat Model

| Threat | Likelihood | Impact | Primary control |
|---|---:|---:|---|
| Unauthorized Telegram user | Medium | High | Non-empty allowlist, startup validation |
| Dashboard/API exposed beyond localhost | Medium | High | Localhost bind, Docker localhost publish |
| LLM prompt injection through notes/files | Medium | High | Delimited prompts, no tool execution from retrieved text |
| Prompt injection / egress via web content | Medium | High | Web off by default; returned content is data, never instructions; no auto-act |
| LLM hallucinated tool/action schema | Medium | High | Tool schemas, Pydantic validation, policy engine |
| Accidental destructive write | Medium | High | Confirm-first tier: pending proposal + explicit confirmation |
| Agent runs an unsafe destructive/egress action without approval | Medium | High | Code-enforced action tier; model cannot self-classify as auto |
| Sensitive content in logs | Medium | Medium | Log metadata by default, redact prompt/response unless debug |
| External LLM data leakage | Low-Medium | High | Disabled by default, explicit opt-in, provider disclosure |
| Dependency compromise | Low | Medium | Pinned dependencies, audit before release |

## Transport Rules

### Telegram

- `TELEGRAM_BOT_TOKEN` is required only when Telegram is enabled.
- `TELEGRAM_ALLOWED_USER_IDS` must be non-empty when Telegram is enabled.
- Empty allowlist is a startup configuration error.
- Messages from unlisted users are rejected without invoking LLMs or tools.
- Telegram user ID must be carried into command/tool execution as the actor.

### Dashboard and REST API

- Default bind host: `127.0.0.1`.
- Docker publish form: `127.0.0.1:8000:8000`.
- Dashboard remains read-only unless a later authenticated local-write spec is
  approved.
- REST endpoints must not pretend `user_id=0` is authentication. Either use a
  real actor from the local session/transport or keep endpoints read-only and
  local.

## LLM Tool Security

The LLM may call Atenas tools. It may not call repositories, services, Python
functions, shell commands, or filesystem paths directly.

A proposed tool call is untrusted until deterministic code validates it. The
**action tier** then decides execution, and the tier is set by code from the
tool's declared category — the model cannot self-classify or set confirmation
flags. Auto-tier writes execute directly and are audit-logged; confirm-first
actions are not executable until the human and policy gates pass.

### Tool classes

| Tool class | Examples | Rule |
|---|---|---|
| Read / search | status, today, week, list assignments, search notes, retrieve sources | Allowed after Telegram allowlist validation |
| Compute | generate plan, suggest next task, explain deadline risk, detect duplicates | Allowed after auth; deterministic service does the computation |
| Act (auto) | add assignment, set status, set hours, add note, add shift, add class | Validated, executed directly, audit-logged |
| Act (confirm-first) | delete/clear/bulk-remove, deduplicate, archive, external message, export | Pending proposal only; code validates, human confirms, policy approves |
| Web (guarded) | web search/fetch | Off by default; egress + untrusted content; never grants tool permissions or triggers writes |
| System | health, local LLM status, safe config summary | Read-only; never reveal secrets |

### Write contract

Reversible local writes (auto tier) execute after validation; the audit log is
the control. Destructive and egress actions (confirm-first tier) must follow
this path:

```text
authenticated user
  -> agent chooses a confirm-first tool
  -> validated tool arguments
  -> natural-language labels resolved to stable IDs
  -> pending action summary shown in Telegram
  -> explicit "yes" confirmation
  -> policy engine check
  -> service execution
  -> audit log
```

The LLM never sets confirmation flags. Code sets confirmation only after the
authenticated user confirms in Telegram.

### Critical Action Classes

The following always require human confirmation before execution:

- Destructive changes: deletes, deduplication, archive operations, bulk clears.
- External communication or data export.
- Configuration changes.
- Sensitive data egress to an external LLM provider or the web.
- Any action where deterministic validation cannot uniquely resolve the target.

Reversible, local, low-risk writes (auto tier) do **not** require prior
confirmation; they are validated, policy-checked, executed, and audit-logged.
The audit trail is the control for this tier. Any action whose tier is uncertain
defaults to confirm-first.

## Forbidden Actions

The policy engine must unconditionally block:

```python
FORBIDDEN_ACTIONS = frozenset({
    "shell_exec",
    "modify_source_code",
    "edit_env_file",
    "read_ssh_keys",
    "read_credentials",
    "install_package",
    "delete_file_silent",
    "change_permissions",
    "unrestricted_fs_access",
    "send_external_message_without_consent",
})
```

## Confirmation-Required Actions

```python
CONFIRMATION_REQUIRED = frozenset({
    "delete_file",
    "overwrite_memory",
    "update_memory",
    "clear_work_schedule",
    "remove_assignment",
    "delete_modules",
    "deduplicate_modules",
    "change_config",
    "send_external_message",
    "archive_plan",
    "archive_note",
    "web_search",
})
```

Confirmation must be explicit (`yes` or `/confirm`). It is carried by code on
`ActionProposal.user_confirmed`, which defaults to `False`. The LLM never sets
that field.

## Default-Deny Policy

Only known allowlisted actions may execute. Unknown action types are denied,
even if they are not listed in `FORBIDDEN_ACTIONS`.

Evaluation order:

1. Forbidden action -> deny.
2. Confirmation-required action without confirmation -> pending/deny.
3. Allowlisted action with valid schema -> allow.
4. Anything else -> deny.

## Prompt Injection Defense

All user text, note text, file text, retrieved source text, and **web content**
is untrusted.

Requirements:

- Do not concatenate untrusted text into prompts without delimiters.
- Mark user text as `<user_input>...</user_input>`.
- Mark retrieved source text as `<source id="...">...</source>`.
- Mark web content as `<web url="...">...</web>`.
- Add an instruction that content inside sources/web is data, not instructions.
- Keep length limits on note/file/web snippets.
- Retrieved and web text may influence answers, not tool permissions, and must
  never trigger a write or an external action on their own.
- Tool calls must be based on the system tool schema, never on instructions
  found inside retrieved or fetched content.

## Web Access

Web search/fetch is **opt-in and disabled by default**. When enabled:

- A web query is **egress**: the query text leaves the machine. Treat it like an
  external-LLM call and never include sensitive records in a query without
  explicit consent.
- Returned content is untrusted data (see prompt-injection defense above).
- The agent must not act on web content directly; any resulting destructive or
  egress action still passes the confirm-first tier.
- Web-derived claims in a reply must be attributed as web sources, kept distinct
  from the user's local notes/files.

## Logging and Privacy

Default logs should include:

- timestamp
- actor/Telegram user ID
- command or tool name
- provider/model
- success/failure
- policy decision
- short payload summary

Default logs should not include full prompt or full response text. Full
prompt/response logging may be enabled only with an explicit debug setting.

Secrets must never be logged:

- `TELEGRAM_BOT_TOKEN`
- external LLM API keys
- `.env` contents
- SSH keys or credential files

## Filesystem Access

Allowed application data roots:

| Directory | Access | Purpose |
|---|---|---|
| `data/` | Read/write | SQLite database |
| `logs/` | Append/read | Audit and LLM logs |
| `inbox/` | Read/write | User-provided staging files |
| registered note/file paths | Read/write according to service policy | Knowledge base |

Never allow LLM tools unrestricted filesystem access. Never read parent
directories, source files, `.env`, SSH keys, or arbitrary user home paths.

## Incident Response

If a forbidden or invalid action is attempted:

1. Block immediately.
2. Log the actor, action type, and policy reason.
3. Notify the allowed Telegram user with a concise blocked-action message.
4. Do not retry automatically.

## Current Enforcement State

Verified on 2026-05-25, re-audited on 2026-06-11:

- The FastAPI app installs a local-only middleware guard by default; Docker
  Compose publishes `127.0.0.1:8000:8000`.
- Telegram startup fails when a bot token is configured without a non-empty
  allowlist.
- Plain Telegram messages route through `AgentLoop` and `ToolRegistry`, with
  Pydantic argument validation, deterministic action tiers, pending
  confirmation for confirm-first tools, and audit logging.
- Web search is disabled by default and, when enabled, is confirm-first egress.
- Retrieval and agent prompts delimit untrusted user/source/web content.
- Slash-command and agent-tool parity is audited in
  `docs/COMMAND_TOOL_PARITY.md`, including command-only support surfaces.

### Known non-compliance (2026-06-11 audit)

All five items identified in the 2026-06-11 audit have been resolved by WP2
of the closure spec (committed 2026-06-12):

- X-Forwarded-For guard now bases its allow decision on the socket peer and
  only uses the forwarded header to make the decision stricter.
- The auto-tier act tools `add_assignment`, `add_note`, `add_class_session`,
  and `add_work_shift` now route through `_gate_action` → `PolicyEngine` and
  emit `action_executed` audit records.
- Pending action status is now accurate: `executed`, `failed`, or `cancelled`
  based on the actual `execute_pending` result.
- `/confirm` is registered as a Telegram command and shares the same code
  path as plain `yes` confirmation.
- All Telegram command handlers emit `command_executed` log events via the
  `_audit_cmd` decorator; `SkillRegistry.dispatch` does the same.

Remaining security follow-up:

- Keep REST endpoints read-only unless a future authenticated local-write spec
  exists. The current `/status` and `/skills` endpoints use a local read actor
  only.
- Add deployment checks around bind host and Compose publishing before any
  release packaging step.
