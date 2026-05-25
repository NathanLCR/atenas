# Atenas Core

Atenas is a Telegram-first, local-running LLM study assistant for a working
student. The app, database, files, dashboard, and REST API are local developer
surfaces. Telegram is the primary product interface.

The current target is an LLM agent that can answer in Telegram and call
controlled Atenas tools for scheduling, planning, notes, retrieval, and data
updates. Slash commands remain supported as fast shortcuts.

The operating doctrine is:

```text
The LLM is a tool-calling agent with strong tools.
Deterministic systems validate and do the heavy lifting.
The human approves only what deletes or leaves the machine.
Everything that changes is logged.
```

## Product Posture

- Single-user and local-only by default.
- Telegram is the main interface and must be allowlist-protected.
- Dashboard and REST API are local support surfaces, not remote services.
- Local Ollama is the default LLM provider. Any external LLM provider is
  explicit opt-in because prompt and tool-result data leave the machine.
- Read tools may run after Telegram allowlist validation.
- Governance is tiered. Reversible, local, low-risk writes (auto tier) resolve
  stable IDs, pass the policy engine, execute through services, and are
  audit-logged — no prior confirmation. Destructive and egress actions
  (confirm-first tier) additionally show a pending action and require explicit
  confirmation before execution. Forbidden actions are blocked. See
  `docs/AGENT_LOOP.md`.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

### CLI

Atenas ships a Click-based CLI accessed via the `atenas` command:

```bash
atenas doctor        # Check DB, Ollama, config, Telegram, web tools
atenas traces        # Show recent agent trace records (--limit N)
atenas tui           # Launch the terminal TUI dashboard
```

Install the CLI with `pip install -e .` after creating the venv.

### Terminal UI

Atenas also has a local read-only terminal UI for quick inspection without the
web dashboard:

```bash
.venv/bin/python -m app.tui
# or after pip install -e .
atenas tui
```

The TUI is a local support surface. It reads the same SQLite data through core
services and does not execute writes, LLM act tools, web search, or exports.

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
  `/dashboard/files`, `/dashboard/search`, `/dashboard/retrieval`,
  `/dashboard/traces`,
  `/dashboard/logs`, `/dashboard/llm`.

## Current Docs

- `docs/AGENT_LOOP.md` is the canonical contract for the agent loop and the
  action-tier governance model. Read it first.
- `docs/PRODUCT_SPEC.md` defines the product posture.
- `docs/ARCHITECTURE.md` defines the tool-agent architecture.
- `docs/AGENT_POLICY.md` defines agent behavior and tool-use rules.
- `docs/SECURITY.md` defines the local-only and Telegram security contract.
- `docs/REQUIREMENTS.md` defines functional and non-functional requirements.
