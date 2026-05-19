# Atenas — Documentation

## What's in this folder

Core spec docs are in `docs/`, with phase and code-map material in
subdirectories:

```text
docs/
├── HANDOFF.md                 Current handoff and next implementation target
├── HANDOFF_NL_INTERFACE.md    Telegram LLM tool interface handoff
├── PRODUCT_SPEC.md            Product posture
├── REQUIREMENTS.md            Functional and non-functional requirements
├── ARCHITECTURE.md            Target tool-agent architecture
├── AGENT_POLICY.md            LLM tool-agent behavior and safety
├── SECURITY.md                Local-only, Telegram, and tool security
├── DATA_MODEL.md              SQLite schema and data entities
├── SCHEMAS.md                 LLM/action schemas
├── ROADMAP.md                 Historical phase roadmap
├── phases/                    Phase specs
├── codex/                     Older Codex handoffs/prompts
└── code-map/                  Developer architecture map
```

## Current Direction

Atenas is local-running and Telegram-first. Plain Telegram messages should be
handled by an LLM agent with controlled Atenas tools. Slash commands remain
supported as shortcuts.

Dashboard and REST API routes are local support surfaces and should not be
exposed directly on a LAN or public host.

## How to Use These Docs

For implementation work, read in this order:

1. `HANDOFF.md`
2. `PRODUCT_SPEC.md`
3. `ARCHITECTURE.md`
4. `SECURITY.md`
5. `AGENT_POLICY.md`
6. `REQUIREMENTS.md`
7. `HANDOFF_NL_INTERFACE.md`
8. Relevant `docs/code-map/` files

Do not rely on historical test counts. Run the suite in the current workspace.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
```

## Historical Material

Some older docs remain useful for context, especially the phase specs and the
original build prompt. When older docs conflict with the 2026-05-19 product
posture, the current canonical docs listed above win.
