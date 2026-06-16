# Agent Best-Practices Research (2026-06-16)

## Purpose

A deep-research pass on current best practices for LLM tool-calling agents —
design patterns, reliability, tool design, context engineering, memory, and
conversational usability — distilled into what is worth bringing to Atenas.

Atenas is a constrained target: a **local, weak Ollama model**, **Telegram-first**,
single-user, with a governed tool-calling loop (`docs/AGENT_LOOP.md`). Findings
are therefore weighted toward reliability, tight context, strong tool scaffolding,
and graceful failure — not frontier-model multi-agent orchestration.

Each section states what the sources converge on, then the implication for
Atenas. The concrete work is specified in
`docs/superpowers/specs/2026-06-16-agent-best-practices-enhancement-spec.md`.

## 1. Keep the agent simple; favor strong scaffolding over autonomy

Sources converge on: most production value comes from **simple, composable
patterns** (single tool-calling loop, routing, prompt-chaining), not elaborate
autonomous multi-agent systems. Add autonomy only when a simpler workflow
demonstrably fails. Long-running single-threaded agents that carry full context
tend to beat naive multi-agent designs, which fragment context and produce
conflicting actions ("share context"; "actions carry implicit decisions").

Implication for Atenas: the existing single bounded loop with strong
deterministic tools is already the recommended shape. Do **not** add
multi-agent orchestration. Invest instead in the loop's reliability and the
quality of its tools and context.

## 2. Tool design: fewer, higher-impact tools that return curated context

Sources (Anthropic "writing tools for agents", and distillations) agree:

- Prefer **fewer, consolidated, high-impact tools** over many thin ones; too
  many tools bloat the prompt and confuse selection. Tool metadata alone can
  consume 20–40% of a context window.
- **Tool descriptions are prompts.** Clear names, clear parameter names,
  unambiguous descriptions. Namespace related tools.
- Tools should **return meaningful, curated context, not raw dumps.** Implement
  **pagination, truncation, and filtering** with sensible defaults.
- Make **response verbosity configurable** ("concise" vs "detailed") so the
  agent spends tokens only when needed.
- **Error messages should steer the agent** toward a valid next action (e.g.,
  list the candidate matches on an ambiguous lookup) rather than dead-end.
- **Evaluate tools** with realistic tasks and iterate.

Implication for Atenas: tools already return a human message plus structured
`data`. Add (a) consistent pagination/limit/truncation defaults on list/read
tools, (b) optional concise/detailed verbosity, and (c) disambiguation-rich
error messages from the ID/label resolvers. These matter more, not less, for a
small context window.

## 3. Context engineering: budget the window, compact rather than drop

Sources treat the context window as a scarce, actively-managed resource:

- Keep the **system prompt lean** and unambiguous; mark untrusted data clearly.
- **Curate tool results** before they re-enter context.
- For long conversations, **compact/summarize** older history into a running
  summary instead of silently dropping turns.
- Prefer **just-in-time retrieval** over preloading everything.
- Track token budgets explicitly per model.

Implication for Atenas: the loop currently keeps the last 12 messages and
truncates each to 2000 chars — lossy and not budget-aware. Introduce a
**model-profile-aware prompt budget** and **history compaction** (summarize
older turns) so a weak, small-context model keeps the goal without overflow.
This aligns with the roadmap's "Budgeted prompt assembly" phase.

## 4. Reliability: structured output + a bounded self-correction step

Across reliability/guardrail sources:

- Use **structured/constrained outputs** to make parsing deterministic.
- The highest-impact post-LLM pattern is a **self-correction loop**: when output
  fails validation, feed the error back and let the model revise **once**,
  rather than returning the failure to the user.
- Apply **input/output guardrails** (policy, format, PII) around the model.
- Bound everything (iterations, retries) to avoid runaway loops.

Implication for Atenas: today a malformed tool-decision JSON ends the turn with
"I could not get a valid tool decision." For a weak local model this is the
single biggest reliability gap. Add (a) **Ollama structured output** (`format`
= JSON schema) to reduce malformed decisions at the source, and (b) **one
bounded repair re-ask** with the validation error as a corrective hint before
falling back. Keep the hard iteration cap.

## 5. Human-in-the-loop: match oversight to risk (Atenas already does this)

Sources recommend **confidence/risk-based routing of oversight**: synchronous
confirmation for high-stakes, irreversible actions (delete, external sends);
asynchronous audit for low-risk, reversible actions. Provide **undo, cancel,
and override**.

Implication for Atenas: the action-tier model (auto / confirm-first / forbidden)
with audit logging already embodies this and is ahead of much of the field. The
missing usability piece is **undo**: auto-tier writes are reversible in
principle (audit captures before/after) but the user has no one-step undo.

## 6. Memory: compact, capped, consented semantic profile

Memory sources distinguish **semantic** (stable facts/preferences about the
user), **episodic** (what happened in past runs), and **working** memory. Best
practices: keep long-term memory **compact, capped, human-readable**; write
memory **only from what the user has actually said** (causality); store
**sensitive data with consent** and support **selective forgetting**.

Implication for Atenas: `MemoryManager` already stores items with
`inferred`/`sensitive` flags and conflict detection. The gap is a **compact,
capped semantic user-profile** (study habits, recurring constraints,
preferences) surfaced into agent context, governed by the existing
inferred/sensitive/consent rules. Lower priority; aligns with the roadmap's
"Approved skill memory" (context-only, never grants permissions).

## 7. Conversational UX: transparency, progress, graceful failure

Conversational-UX sources emphasize:

- **Transparency**: show what the agent is doing and why; surface which tools/
  data were used.
- **Progress signaling**: emit a bridging message ("one moment, checking…")
  when work takes time; stream where possible.
- **Graceful failure & off-ramps**: recover from misunderstandings, never hide
  failures, offer a clear next step.
- **Confirm / undo / cancel / override** affordances.

Implication for Atenas (Telegram, no token streaming): add a **"working on it"
bridging message** for multi-tool turns, optional **transparency footer** naming
the tools used, and keep failures honest with a concrete next step (the agent
policy already forbids hiding failed writes). These are cheap, high-value
Telegram-native touches.

## 8. Evaluation & observability: trajectory-level regression tests

Sources stress evaluating agents on **trajectories** (did it pick the right
tools in the right order?), not just final answers, plus **observability/tracing**
in production.

Implication for Atenas: it already records rich SQLite traces
(`agent_traces` / `agent_trace_steps`). The gap is an **offline eval harness**:
a fixed set of representative Telegram messages with expected tool trajectories,
run against a **mocked/scripted model**, to catch regressions in tool selection
and loop control deterministically. Complements the roadmap's "Trace replay and
search".

## Priority for Atenas

1. Reliability self-correction + structured output (§4) — biggest win for a weak model.
2. Tool result curation, pagination, steering errors (§2).
3. Context budget + history compaction (§3).
4. Conversational UX: progress, transparency, undo (§5, §7).
5. Agent eval harness (§8).
6. Semantic user-profile memory (§6) — later.

## Sources

- [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Cognition — Don't build multi-agents](https://cognition.ai/blog/dont-build-multi-agents)
- [Chip Huyen — Agents](https://huyenchip.com/2025/01/07/agents.html)
- [Writing effective tools for AI agents (lessons from Anthropic)](https://blog.agentailor.com/posts/writing-tools-for-ai-agents)
- [Agents at work: the 2026 playbook for reliable agentic workflows](https://promptengineering.org/agents-at-work-the-2026-playbook-for-building-reliable-agentic-workflows/)
- [Arthur — Best practices for building agents: guardrails](https://www.arthur.ai/blog/best-practices-for-building-agents-guardrails)
- [Galileo — Human-in-the-loop oversight for AI agents](https://galileo.ai/blog/human-in-the-loop-agent-oversight)
- [AI agents 2026: tools, memory, evals, guardrails](https://andriifurmanets.com/blogs/ai-agents-2026-practical-architecture-tools-memory-evals-guardrails)
- [Phil Schmid — Memory in agents](https://www.philschmid.de/memory-in-agents)
- [The Conversational UX Handbook (2025)](https://medium.com/@avigoldfinger/the-conversational-ux-handbook-2025-98d811bb6fcb)
- [Ably — Reliable, resumable token streaming for AI UX](https://ably.com/blog/token-streaming-for-ai-ux)
- [awesome-harness-engineering (patterns, evals, memory, MCP, observability)](https://github.com/ai-boost/awesome-harness-engineering)
