# Atenas — Contributor Instructions

## Current Direction

Atenas is a local-running, Telegram-first LLM study assistant.

Primary interface:

- Telegram slash commands.
- Plain Telegram messages handled by an LLM agent with Atenas tools.

Secondary surfaces:

- Local FastAPI API.
- Local read-only dashboard.

Do not treat the dashboard/API as remote product surfaces unless a future spec
adds authentication and deployment hardening.

## Rules

- Do what has been asked; keep scope tight.
- Read relevant files before editing.
- Keep docs, tests, and code aligned.
- Do not commit secrets, `.env`, tokens, local databases, generated tool state,
  or dependency caches.
- Keep files under 500 lines unless there is a documented reason.
- Validate input at system boundaries.
- Preserve existing user changes in the worktree.
- Prefer small, reviewable changes.

## Architecture Rules

- Dependencies flow `app -> core`, not `core -> app`.
- `app/` wires Telegram, FastAPI, config, startup, and response formatting.
- `core/` owns services, policy, data models, repositories, retrieval, and LLM clients.
- Settings are injected into core services. Do not import `app.config` inside `core/`.
- The LLM sees tool schemas, not service/repository objects.
- Tool handlers call services; they do not duplicate business logic.

## Telegram and LLM Rules

- Telegram is the main product interface.
- Telegram allowlist applies before command handling, LLM calls, retrieval, or tools.
- Empty Telegram allowlist is invalid when Telegram is enabled.
- Plain messages should route to the LLM tool agent.
- Slash commands remain deterministic shortcuts and must keep working.
- Local Ollama is the default LLM provider.
- External LLM providers are opt-in data egress and must be documented clearly.

## Tool Safety

Read tools may run after allowlist auth.

Write tools must:

1. Validate arguments.
2. Resolve natural-language titles/modules to stable IDs.
3. Create a pending action summary.
4. Ask for explicit Telegram confirmation.
5. Run the policy engine after confirmation.
6. Execute through core services.
7. Log the outcome.

The LLM never sets confirmation flags and never executes writes directly.

## Local-Only Surface Rules

- Dashboard/API bind to `127.0.0.1` by default.
- Docker Compose publishes to localhost only.
- Dashboard stays read-only unless a future authenticated write spec exists.
- REST endpoints must not use fake user identity such as `user_id=0` for
  privileged behavior.

## Build and Test

Python project. Do not run npm build/test commands for Atenas.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
```

Tests should mock LLM providers and use isolated settings/databases. Do not let
tests fall back to the local `.env` or real local database.

## Docs to Read First

1. `docs/AGENT_LOOP.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/AGENT_POLICY.md`
6. `docs/REQUIREMENTS.md`
