# Atenas — Documentation

## Canonical doc set

This folder holds one source of truth per concern. There are no handoff,
phase, or build-prompt docs — those caused the divergence we removed.

```text
docs/
├── GETTING_STARTED.md
│                     Fresh-clone setup: install, Ollama models, Telegram, .env
├── AGENT_LOOP.md     The agent loop + action-tier governance contract (canonical)
├── PRODUCT_SPEC.md   What Atenas is, who it's for, success criteria
├── ARCHITECTURE.md   How the agent loop, tools, and layers are structured
├── AGENT_POLICY.md   Agent behavior, tool-use rules, planning/retrieval/web rules
├── SECURITY.md       Local-only posture, action tiers, prompt-injection & web defense
├── REQUIREMENTS.md   Functional and non-functional requirements
├── DATA_MODEL.md     SQLite schema and data entities
├── SCHEMAS.md        LLM/action schemas
├── CONTEXT_MANAGEMENT.md
│                     Context, state, and memory layers across timescales
├── DECISIONS.md      Dated architecture decision records
└── COMMAND_TOOL_PARITY.md
                      Slash-command to agent-tool parity audit
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
deterministic shortcuts. Dashboard/API/TUI are local support surfaces only.

The terminal UI runs with `.venv/bin/python -m app.tui`. It is read-only in its
first version and must not call act tools or the LLM agent loop until a separate
confirmation and audit contract exists for terminal-originated writes.

## Current implementation snapshot

Verified on 2026-05-25:

- Plain Telegram messages use `AgentLoop` plus `ToolRegistry`.
- Slash commands remain deterministic shortcuts.
- The agent-facing tool catalog covers status, schedule overviews, deadlines,
  availability, modules, assignments, classes, shifts, notes, retrieval, memory,
  local LLM status, planning, deadline risk, duplicate detection, reversible
  local writes, confirm-first destructive actions, and opt-in web search.
- Dashboard, API, and TUI are local support surfaces; the dashboard and TUI are
  read-only.
- Retrieval syncs registered notes/files incrementally into SQLite
  `retrieval_chunks` plus FTS5, with lexical fallback.
- Editable package discovery is configured in `pyproject.toml`; runtime data
  directories are excluded from the package set.
- FR-06 planning acceptance coverage exists in
  `tests/academic/test_planner_acceptance.py`.
- Work-shift `fatigue_level` is accepted through the shared service,
  `/add_shift`, and the `add_work_shift` agent tool.
- Pending actions can be reviewed with `/pending` and cancelled with
  `/cancel_pending`; plain `yes` and `no` confirmations remain supported.
- Slash-command parity is audited in `docs/COMMAND_TOOL_PARITY.md` and guarded
  by `tests/test_command_tool_parity.py`.

A full read-only audit on 2026-06-11 found a set of implementation defects and
governance gaps behind the contracts above (tool crashes, policy/audit bypass
on auto-tier `add_*` tools, a spoofable local-only guard decision, and
pending-action status accuracy). The canonical docs now record those gaps
where they contradict previous claims, and the fixes are specified in
`docs/superpowers/specs/2026-06-12-v1-defect-and-governance-closure-spec.md`.

## Current gap specs

The defect and governance closure spec (current priority) lives at
`docs/superpowers/specs/2026-06-12-v1-defect-and-governance-closure-spec.md`.

The earlier implementation gap and packaging spec lives at
`docs/superpowers/specs/2026-05-24-atenas-v1-gap-and-packaging-spec.md`.
It records that the 2026-05-25 verification closed planning acceptance
coverage, fatigue/write-path input, slash-command parity audit, documentation
drift, and packaging checks. Post-v1 backup/export work remains separate from
the v1 operational SQLite source-of-truth contract.

## Superpowers roadmap

Superpowers implementation status is summarized in
`docs/superpowers/README.md`. Use that roadmap to distinguish live phase work
from archival implementation plans before starting new hardening or refactor
work.

## Local-model agent hardening

The local-model agent runtime hardening spec lives at
`docs/superpowers/specs/2026-05-24-local-model-agent-runtime-state-spec.md`,
with an implementation breakdown and starter prompt in
`docs/superpowers/plans/2026-05-24-local-model-agent-runtime-state.md`.
It captures the framework patterns worth borrowing for Atenas: durable pending
actions, model profiles, context-budgeted prompt assembly, deterministic tool
selection, richer pending-action review, and trace replay.

The Hermes-inspired hardening spec lives at
`docs/superpowers/specs/2026-05-24-hermes-inspired-agent-hardening-spec.md`,
with implementation phases and a starter prompt in
`docs/superpowers/plans/2026-05-24-hermes-inspired-agent-hardening.md`.
It covers the safe Hermes patterns for Atenas: toolsets, approved skill memory,
backup/restore, local model profile config, session search, and a future
channel adapter boundary.

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
