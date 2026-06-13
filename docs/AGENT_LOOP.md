# Atenas — Agent Loop Contract

## Status

Canonical contract as of 2026-05-20, verified against the current code on
2026-05-24. This is the single source of truth for how the Telegram LLM agent
behaves. When `ARCHITECTURE.md`, `AGENT_POLICY.md`, or `SECURITY.md` describe
agent behavior, they defer to this file. Codex, Claude Code, and OpenCode must
all follow this contract to keep the implementation from diverging.

## Why this exists

The earlier design used a single-shot **intent classifier**: one LLM call mapped
each message to a fixed menu of ~20 intents, then a hardcoded router ran a fixed
handler. That made Atenas a static-data desk, not an agent:

- Asking it to *delete duplicate modules* returned the same list, because there
  was no act-tool — it degraded to the nearest read intent.
- Saying *"let's review that"* shifted to "which subject do you want to study?",
  because the classifier is stateless and re-matched the word to the nearest
  intent with no memory of the goal.

Atenas uses a real **tool-calling agent loop** for the canonical Telegram
natural-language path. The local model is weak at reasoning, so we compensate
with **strong tools**, not more guardrails. `NLRouter` and `NLClassifier` remain
legacy compatibility surfaces only; new product behavior belongs in
`AgentLoop` and `ToolRegistry`.

## The Loop

```text
user message
  -> allowlist check
  -> agent receives: conversation context + tool schemas
  -> LOOP (bounded):
       agent picks a tool and arguments
       -> code validates arguments and resolves labels to stable IDs
       -> code checks the action tier (auto / confirm-first / forbidden)
       -> tool executes (or pends for confirmation)
       -> structured result returned to the agent
       -> agent decides: call another tool, or answer
  -> agent writes a concise Telegram reply
  -> audit log records every tool call and outcome
```

The agent carries the user's **goal** across iterations and across turns, so a
follow-up like "yes, do that" or "let's review the duplicates" continues the
task instead of being re-classified from scratch.

### Loop guardrails (for a weak local model)

- **Tools do the heavy lifting.** The planner computes slots, the dedup tool
  finds the duplicates, the deadline-risk tool scores. The model decides
  *whether to apply*, not *how to compute*. Few decisions, well-scaffolded.
- **Bounded iterations.** A hard cap on tool calls per turn. On reaching it, the
  agent stops and summarizes/asks instead of looping forever.
- **Deterministic fallback.** If the model fails to produce a valid tool call,
  fall back to a safe read or a clarifying question — never to a silent mutation.
- **Tool results are authoritative** over model memory.

## Three Tool Categories ("armas poderosas")

| Category | Purpose | Examples |
|---|---|---|
| **Read / search** | Pull current state and context | today/week overview, list assignments/modules/shifts, search notes, retrieve sources |
| **Compute / cross-reference** | Deterministic heavy lifting | study planner, **duplicate detector**, deadline-risk scoring, availability math |
| **Act** | Change state or reach outside | create/update/delete records, **deduplicate**, set status, add class/shift, schedule, send |

Web search is **not** a read tool. It is registered in its own guarded `web`
category at the confirm-first tier (a query is egress), and only when web
access is enabled. See "Web Use" below; `SECURITY.md` lists `web_search` in
`CONFIRMATION_REQUIRED`.

Tools have validated argument schemas and structured result schemas. The LLM
calls tools only; it never touches services, repositories, files, or the shell.

## Action Tiers (governance)

The execution tier is decided by **code**, from the tool's declared category —
never by the model. The model cannot set confirmation flags or bypass a gate.

| Tier | What | Rule |
|---|---|---|
| **Auto** | Reversible, local, low-risk writes: create/update note, set status, set hours, add assignment/class/shift, link module | Agent executes directly, reports result, **audit-logs the change** |
| **Confirm-first** | Destructive (delete, clear, bulk-remove, dedup-delete) **or** egress (send external message, export, external-LLM with sensitive context) | Agent shows a pending summary, waits for explicit `yes`/`no`, then executes + logs |
| **Forbidden** | shell, source edits, secret/credential reads, unrestricted filesystem, sending data out without consent | Policy engine blocks unconditionally; default-deny on unknown actions |

Everything that mutates state produces an **audit record** of what changed
(actor, tool, arguments summary, outcome, and before/after where meaningful).
This is the "me dê log do que mudou" requirement — agency is traded for a clear
trail, not for prior approval on every action.

## Web Use

Web is **opt-in and disabled by default**. When enabled:

- A web query is **egress** — the query text leaves the machine. Treat it like
  an external-LLM call.
- Returned web content is **untrusted data, never instructions.** The agent must
  not follow commands embedded in fetched pages and must not let web content
  grant tool permissions or trigger writes on its own.
- Any *action* prompted by web content still passes the normal action tiers
  (delete/egress still confirm).
- Web-derived claims in a reply must be attributed as web sources, distinct from
  the user's local notes/files.

## Confirmation Mechanics

- Confirmation is explicit (`yes` / `/confirm`) and is carried on
  `ActionProposal.user_confirmed`, which defaults to `False`.
- **Code sets that flag, never the model.**
- A confirmation belongs to the actor who proposed it; if the Telegram user
  changes, the pending action is cancelled.

## What Stays the Same

- Telegram-first; slash commands remain deterministic shortcuts.
- Local Ollama is the default provider; external providers are opt-in egress.
- Dependencies flow `app -> core`. The LLM sees tool schemas, not service objects.
- Spec-driven development — but specs describe the loop and tiers above, not a
  fixed intent menu.

## Current Implementation State

The canonical path is implemented in `core/nl/agent.py` and
`core/nl/tools.py`. Plain Telegram messages build `AgentLoop` plus
`ToolRegistry`; the loop is bounded, records traces, logs LLM calls, and stores
pending confirm-first actions in SQLite through `AgentRuntimeStore`, with
Telegram `user_data` used only as a speed cache during the process lifetime.

Shipped tool-loop behavior:

1. **Expanded tool catalog** — read, compute, act, system, and opt-in web tools
   are registered through `ToolRegistry`.
2. **Web tool** — `web_search` is registered only when `web_enabled=True`
   (default off). Query text is egress; returned content is wrapped as `<web>`
   untrusted data; it never triggers automatic writes.
3. **archive_note** — wired as an `ActionTier.CONFIRM_FIRST` act tool.
   `export_data` is out of v1 scope.
4. **Audit before/after** — confirm-first mutations such as `delete_modules`,
   `deduplicate_modules`, `archive_note`, and `update_memory` capture prior
   state in `before_state` and post-execution state in `after_state` where
   meaningful, with sensitive content summarized or redacted.
5. **Toolset visibility** — `core/nl/toolsets.py` groups tools into named
   toolsets (safe, destructive, egress, readonly, dev-local). The agent only
   sees tools in the toolsets selected for the current message; destructive
   and egress toolsets are added per message by deterministic request-marker
   matching, never by the model.

All defects identified by the 2026-06-11 audit are resolved as of 2026-06-13.
See `docs/superpowers/specs/2026-06-12-v1-defect-and-governance-closure-spec.md`
for the full record.
