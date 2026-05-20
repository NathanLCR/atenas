# Atenas — Documentation

## Canonical doc set

This folder holds one source of truth per concern. There are no handoff,
phase, or build-prompt docs — those caused the divergence we removed.

```text
docs/
├── AGENT_LOOP.md     The agent loop + action-tier governance contract (canonical)
├── PRODUCT_SPEC.md   What Atenas is, who it's for, success criteria
├── ARCHITECTURE.md   How the agent loop, tools, and layers are structured
├── AGENT_POLICY.md   Agent behavior, tool-use rules, planning/retrieval/web rules
├── SECURITY.md       Local-only posture, action tiers, prompt-injection & web defense
├── REQUIREMENTS.md   Functional and non-functional requirements
├── DATA_MODEL.md     SQLite schema and data entities
└── SCHEMAS.md        LLM/action schemas
```

## Current direction

Atenas is local-running and Telegram-first. Plain Telegram messages are handled
by an **LLM tool-calling agent loop** — the model calls a tool, observes the
result, and decides the next step, carrying the goal across turns. The local
model is weak at reasoning, so it is given strong tools (read, compute, act)
rather than more guardrails.

Governance is tiered: reversible local writes run directly and are audit-logged;
destructive and egress actions require explicit confirmation; forbidden actions
are blocked. Web access is opt-in and guarded. Slash commands remain as
deterministic shortcuts. Dashboard/API are local support surfaces only.

When any doc describes agent behavior, `AGENT_LOOP.md` is authoritative. All
contributors — including Codex, Claude Code, and OpenCode — follow it to keep
the implementation from diverging again.

## How to read

For implementation work, read in this order:

1. `AGENT_LOOP.md`
2. `PRODUCT_SPEC.md`
3. `ARCHITECTURE.md`
4. `SECURITY.md`
5. `AGENT_POLICY.md`
6. `REQUIREMENTS.md`

Do not rely on historical test counts. Run the suite in the current workspace.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
```
