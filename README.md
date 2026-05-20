# Atenas Core

Atenas is a Telegram-first, local-running LLM study assistant for a working
student. The app, database, files, dashboard, and REST API are local developer
surfaces. Telegram is the primary product interface.

The current target is an LLM agent that can answer in Telegram and call
controlled Atenas tools for scheduling, planning, notes, retrieval, and data
updates. Slash commands remain supported as fast shortcuts.

The operating doctrine is:

```text
LLM proposes.
Deterministic systems validate.
Human approves critical actions.
```

## Product Posture

- Single-user and local-only by default.
- Telegram is the main interface and must be allowlist-protected.
- Dashboard and REST API are local support surfaces, not remote services.
- Local Ollama is the default LLM provider. Any external LLM provider is
  explicit opt-in because prompt and tool-result data leave the machine.
- Read tools may run after Telegram allowlist validation.
- LLM-originated writes must resolve stable IDs, show a pending action, require
  explicit confirmation, pass the policy engine, execute through services, and
  log the result.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

The intended local URL is `http://127.0.0.1:8000`. Do not expose the dashboard
or REST API directly on a LAN or public host.

## Test

```bash
.venv/bin/pytest -q
```

Do not rely on historical test counts in docs. Re-run the suite in the current
workspace before implementation work.

## Docker

Docker is for local development. Compose publishing should bind to localhost
only, for example `127.0.0.1:8000:8000`.

```bash
docker-compose up
```

## Main Surfaces

- Telegram: slash commands plus the planned LLM tool-agent conversation path.
- Local API: `/health`, `/status`, `/skills`.
- Local dashboard: `/dashboard/`, `/dashboard/week`, `/dashboard/deadlines`,
  `/dashboard/plan`, `/dashboard/data`, `/dashboard/notes`,
  `/dashboard/files`, `/dashboard/search`, `/dashboard/logs`, `/dashboard/llm`.

## Current Docs

- `docs/AGENT_LOOP.md` is the canonical contract for the agent loop and the
  action-tier governance model. Read it first.
- `docs/PRODUCT_SPEC.md` defines the product posture.
- `docs/ARCHITECTURE.md` defines the tool-agent architecture.
- `docs/AGENT_POLICY.md` defines agent behavior and tool-use rules.
- `docs/SECURITY.md` defines the local-only and Telegram security contract.
- `docs/REQUIREMENTS.md` defines functional and non-functional requirements.
