# Agent Best-Practices Enhancement Spec

## Status

Proposed (2026-06-16). Not yet implemented. Derived from
`docs/superpowers/research/2026-06-16-agent-best-practices.md`. Defers to
`docs/AGENT_LOOP.md` for the loop and governance contract; this spec only adds
capability inside that contract. Work packages are independent and ordered by
value-for-effort for a weak local model.

## Purpose

Translate current LLM-agent best practices into concrete, bounded improvements
to the Atenas Telegram tool-calling agent. The constraints are fixed: local
weak Ollama model, Telegram-first, single-user, governed action tiers, and
`app -> core` dependency flow. Each work package below names the real files it
touches and falsifiable acceptance criteria.

## Current Verified State

- Canonical loop in `core/nl/agent.py` (`AgentLoop`) + `core/nl/tools.py`
  (`ToolRegistry`); bounded at `max_tool_calls=5`.
- Tools return `StructuredToolResult` (`ok`, `message`, `data`, `executed`,
  `pending`); 24 tools across read/compute/act/system/web.
- Toolset visibility by deterministic request-marker matching
  (`core/nl/toolsets.py`).
- Durable threads + pending actions in SQLite (`core/nl/runtime_state.py`).
- Rich traces in `agent_traces` / `agent_trace_steps` (`core/nl/traces.py`).
- Confirm-first mutations capture `before_state` / `after_state`.
- History handling: last 12 messages, each truncated to 2000 chars (lossy).
- Malformed tool-decision JSON ends the turn with a generic error (no repair).

## WP1: Reliable tool-decision parsing (structured output + one repair)

**Problem.** For a weak local model the dominant failure is a malformed or
non-conforming decision JSON. Today `_parse_decision()` returning `None` ends
the turn with "I could not get a valid tool decision." No structured-output
constraint, no repair attempt. (Best practice §4.)

**Required behavior.**

1. Request structured output from Ollama where supported: pass a JSON schema /
   `format` for the `AgentDecision` shape on the decision call in
   `core/nl/agent.py` (via the client in `core/llm/client.py`). Degrade
   gracefully if the model/endpoint ignores `format`.
2. On a parse/validation failure, perform **exactly one** bounded repair
   re-ask: re-prompt with the original context plus a short corrective hint
   containing the validation error and the required JSON shape. This repair
   does **not** count against `max_tool_calls` but is itself capped at one.
3. Only after the repair fails does the loop fall back to the existing safe
   message. The fallback must never be a silent mutation (unchanged contract).
4. Record the repair attempt in the trace (new step flag or status), so the
   eval harness (WP6) and doctor can surface malformed-rate.

**Acceptance criteria.**

- A scripted model that emits one malformed JSON then a valid tool call
  completes the task within one turn (repair succeeds), with the repair visible
  in the trace.
- A scripted model that emits two malformed responses returns the safe
  fallback, performs no mutation, and the trace status reflects the failure.
- When `format` is supplied, the client sends it; tests assert it is passed and
  that behavior is unchanged when the backend ignores it.
- Existing agent-loop tests still pass.

## WP2: Tool result curation — pagination, limits, and verbosity

**Problem.** List/read tools can return large `message`/`data` payloads into a
small context window; there is no consistent pagination or verbosity control.
(Best practice §2, §3.)

**Required behavior.**

1. Add consistent, validated pagination/limit arguments (e.g., `limit`,
   `offset`) with sensible **defaults and hard caps** to list/search read tools
   in `core/nl/tools.py` (modules, assignments, notes, sources, shifts,
   sessions). Truncation must be explicit and signalled in the result (e.g.,
   `data.truncated = true`, `data.total`).
2. Add an optional `verbosity` argument (`concise` default, `detailed`) to
   high-volume read tools; concise returns only fields the agent needs to act.
3. Keep human `message` text Telegram-short; put full structure in `data`.

**Acceptance criteria.**

- A list tool with more rows than the cap returns the capped set, sets
  `data.truncated=true` and a `data.total`, and never exceeds the cap.
- `verbosity=concise` returns strictly fewer fields than `detailed` for the
  same query; default is concise.
- Pagination arguments are validated (non-negative, bounded) and invalid values
  produce a steering error (WP4), not a crash.

## WP3: Model-profile prompt budget and history compaction

**Problem.** History is capped by count/char truncation, not by a token budget,
and old turns are dropped rather than summarized — the weak model can lose the
goal or overflow. Aligns with the roadmap "Local model profile config" and
"Budgeted prompt assembly" phases. (Best practice §3.)

**Required behavior.**

1. Introduce a **model profile** (context length, prompt-token budget, timeout,
   max history tokens) in settings/core, surfaced in `atenas doctor`. Inject it
   into `AgentLoop` (no `app.config` import in `core/`).
2. Extract prompt assembly out of `AgentLoop.run()` into a dedicated assembler
   that enforces the budget: tools + system + observations + history must fit
   the profile's prompt budget.
3. When history exceeds the budget, **compact** the oldest turns into a short
   running summary (a deterministic, bounded summarizer; LLM summary optional
   and itself budgeted) instead of dropping them. Persist the summary on the
   thread (`runtime_state.py`).
4. Record selection/compaction metadata in the trace.

**Acceptance criteria.**

- Assembled prompt token estimate never exceeds the profile budget for a long
  synthetic conversation; the goal from turn 1 is still represented (via summary)
  after many turns.
- Compaction is deterministic for a seeded fixture and covered by a test.
- `atenas doctor` prints the active model profile (context length, budget,
  timeout).
- Prompt assembly is unit-testable without a live model.

## WP4: Steering tool-error messages and disambiguation

**Problem.** Resolver errors are terse ("Multiple modules match", "Module not
found"), giving the weak model little to recover with. (Best practice §2, §4.)

**Required behavior.**

1. On ambiguous resolution, return the **candidate options** (names + short IDs)
   in both `message` and `data.candidates`, instructing the agent to ask the
   user or pick by ID.
2. On not-found, suggest the closest matches when available.
3. Keep messages concise and action-oriented; never leak internal stack detail.
4. Apply consistently across module/assignment/note resolvers in
   `core/nl/tools.py`.

**Acceptance criteria.**

- An ambiguous title yields a result whose `data.candidates` lists the matching
  records and whose message names them; no mutation occurs.
- A near-miss title yields a not-found result with suggested candidates.
- Resolver behavior is covered by tests for ambiguous, not-found, and exact
  cases.

## WP5: Conversational UX — progress, transparency, and undo

**Problem.** Telegram replies give no progress signal on multi-tool turns, no
visibility into which tools ran, and no one-step undo for reversible auto-tier
writes. (Best practice §5, §7.)

**Required behavior.**

1. **Progress signal.** When a turn will run tools (or exceeds a short latency
   threshold), send a single bridging Telegram message ("Working on it…")
   before the final reply. Implemented in the Telegram layer (`app/bot.py`),
   driven by agent-loop signals; no token streaming required.
2. **Transparency footer (opt-in).** Optionally append a compact "tools used:
   …" footer to replies, gated by a setting (default off to keep replies clean).
3. **Undo.** Add an `/undo` deterministic command and/or an `undo_last_action`
   path that reverses the most recent **auto-tier** write for the actor using
   the audit `before_state`. Undo of confirm-first/destructive actions is out of
   scope (they were already confirmed). Undo itself is audit-logged.

**Acceptance criteria.**

- A multi-tool turn emits exactly one bridging message, then the final reply.
- With the transparency setting on, the footer lists the tools actually
  executed; with it off, replies are unchanged.
- `/undo` after an auto-tier write (e.g., `set_assignment_status`) restores the
  prior value from `before_state`, is audit-logged, and reports the result;
  `/undo` with nothing to undo replies safely.

## WP6: Offline agent evaluation harness (trajectory regression)

**Problem.** No deterministic regression coverage for tool-selection and loop
control; correctness is only checked per-component. (Best practice §8.)

**Required behavior.**

1. Add an eval harness under `tests/` that runs `AgentLoop` against a
   **scripted/mocked model** (no live Ollama) over a fixture set of
   representative Telegram messages.
2. Each fixture asserts the **expected trajectory**: tools called (and order
   where it matters), final action tier, whether a pending action was created,
   and that no unexpected mutation occurred.
3. Cover: a read question, an auto-tier write, a confirm-first proposal + `yes`,
   an ambiguous resolution (WP4), a malformed-then-repaired decision (WP1), and
   a tool-cap stop.
4. Keep it fast and deterministic so it runs in CI (the workflow added in the
   deliverability work).

**Acceptance criteria.**

- The harness runs in CI without Ollama or a Telegram token and is
  deterministic across runs.
- Each scenario fails loudly if the trajectory or governance outcome regresses
  (e.g., a confirm-first tool executing without confirmation).

## WP7 (Later): Compact semantic user-profile memory

**Problem.** No compact, capped, consented profile of stable user preferences/
habits is surfaced to the agent. Aligns with roadmap "Approved skill memory"
(context-only, never grants permissions). (Best practice §6.)

**Required behavior.**

1. Define a compact, **capped, human-readable** user profile built only from
   what the user has stated (causality), via `MemoryManager` with existing
   `inferred`/`sensitive` flags.
2. Surface the profile into agent context within the WP3 budget; never inject
   `sensitive` content into any egress (web/external-LLM) path.
3. Support **selective forgetting** (delete a profile fact), audit-logged.
4. Profile context **never** grants tool permissions or changes action tiers.

**Acceptance criteria.**

- Profile stays within a fixed size/length cap; oldest/least-important facts are
  dropped or summarized when full.
- `sensitive` profile facts are excluded from egress prompts (test-asserted).
- A forget operation removes a fact and is audit-logged.

## Ground Rules For Implementation

- Obey `docs/AGENT_LOOP.md`: code owns action tiers, confirmation, policy, and
  audit; the model never sets confirmation flags. None of these WPs let the
  model self-confirm or self-escalate.
- `app -> core` only; do not import `app.config` in `core/`. Inject the model
  profile and settings.
- Do not add new behavior to `NLRouter` / `NLClassifier` (legacy); extend the
  tool loop and `ToolRegistry`.
- Keep files under 500 lines; this is a natural point to split
  `core/nl/tools.py` and extract prompt assembly from `core/nl/agent.py` (see
  roadmap "Refactor Support").
- Every WP ships with tests that mock the LLM and use isolated settings/DB.
- Update canonical docs (`docs/AGENT_LOOP.md`, `AGENT_POLICY.md`) when a WP
  changes observable agent behavior, and add a `CHANGELOG.md` entry.

## Out Of Scope

- Multi-agent orchestration (research §1 advises against it here).
- Token streaming to Telegram (not supported by the channel; bridging message
  instead).
- Remote/multi-user deployment, new external integrations.
- Undo of confirm-first/destructive or egress actions.
- Replacing Ollama as the default local provider.

## Completion Definition

A work package is complete when its acceptance criteria are met by tests that
run without a live model, canonical docs and `CHANGELOG.md` are updated, and the
roadmap phase status is moved to Done with a one-line current note.
