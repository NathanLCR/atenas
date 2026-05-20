# Atenas Handoff — Propose, Validate, Approve

## Date

2026-05-20

## Status

Active implementation handoff. This document defines the next architecture
direction for Atenas after the Telegram natural-language foundation.

The north star is:

```text
LLM proposes.
Deterministic systems validate.
Human approves critical actions.
```

Use this handoff with:

1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/SECURITY.md`
4. `docs/AGENT_POLICY.md`
5. `docs/REQUIREMENTS.md`
6. `docs/HANDOFF_NL_INTERFACE.md`

## Product Contract

Atenas is a local-running, Telegram-first assistant. The LLM is useful because
it understands messy natural language and can synthesize context. It is not
trusted to mutate state. Mutation belongs to deterministic code and approved
service execution.

The project should behave like this:

```text
Telegram/user input
  -> allowlist/authenticated actor
  -> LLM proposes intent/tool/action
  -> deterministic schema validation
  -> deterministic ID and target resolution
  -> deterministic domain constraints
  -> human approval for critical actions
  -> policy engine/default-deny
  -> core service execution
  -> audit log
  -> user-facing result
```

## Action Classes

| Class | Examples | Rule |
|---|---|---|
| Read | status, today, notes search, retrieval sources | May run after allowlist/auth |
| Planning | study plan, next task, deadline risk | May run after auth; deterministic code owns time blocks and constraints |
| Local write | add assignment, set status, add note | LLM may propose; deterministic code validates; human confirms in v1 |
| Destructive | delete, archive, bulk clear, overwrite | Always requires human approval and policy approval |
| External | send message, export data, external LLM with sensitive context | Always requires explicit human approval |
| Config/system | change config, install package, shell, permissions | Block by default unless a later spec adds a narrow approved path |

For v1, every LLM-originated write is critical.

## Current Implementation Direction

The current transition path may keep `core/nl/` temporarily, but with stricter
meaning:

- `IntentMatch` is only an LLM proposal.
- `ActionProposal` is the validated pending action envelope.
- `user_confirmed` is set only by code after a Telegram `yes`.
- `ActionExecutor` calls `PolicyEngine` before any service handler.
- Service handlers are the only place where persistence changes happen.

Direct helpers named like `execute_write()` should either refuse mutation or be
removed once callers use the confirmed proposal executor.

## Required Next Implementation Steps

1. Keep Telegram startup strict:
   - token plus empty allowlist must fail startup
   - unauthorized users must not invoke LLMs or tools

2. Finish the shared action proposal layer:
   - define proposal builders for every write tool
   - validate arguments before storing pending state
   - resolve natural-language targets to stable IDs
   - reject ambiguous targets without mutation

3. Move all LLM-originated writes onto the same execution path:
   - pending proposal
   - explicit Telegram confirmation
   - policy engine
   - service execution
   - audit log

4. Decide how slash-command writes participate:
   - preserve existing command behavior while refactoring
   - route high-risk slash-command actions through the same policy/approval path
   - document any deterministic low-risk command that intentionally remains direct

5. Lock local-only transports:
   - uvicorn/dashboard/API default to `127.0.0.1`
   - Docker Compose publishes `127.0.0.1:8000:8000`
   - local REST writes must not use fake actor semantics

6. Harden prompt boundaries:
   - delimit user input
   - delimit retrieved sources
   - state that retrieved content is data, not instructions

7. Fix retrieval indexing:
   - no full chunk rebuild on every query
   - use explicit rebuild, incremental indexing, or dirty flags

## Acceptance Tests

Minimum tests before claiming compliance:

- Empty Telegram allowlist plus token fails startup.
- Unauthorized Telegram user does not invoke the LLM/classifier.
- LLM write request stores a pending proposal and does not mutate.
- Confirmation `no` cancels without mutation.
- Confirmation `yes` sets `user_confirmed` in code, not from LLM output.
- Policy check runs before service execution.
- Policy denial prevents service execution.
- Ambiguous title-to-ID resolution rejects without mutation.
- Action audit includes actor, action type, policy decision, outcome, and short payload summary.
- Prompt templates delimit user input and retrieved sources.
- REST/local API does not use `user_id=0` as a privileged actor.
- Retrieval queries do not rebuild all chunks.

## Known Verification Warning

Do not claim a green suite until the pytest/import hang is understood. Recent
local runs hung before collection while importing pytest/Pydantic modules.

Use syntax checks as a floor only:

```bash
.venv/bin/python -m py_compile app/bot.py app/config.py app/main.py core/action_executor.py core/policy_engine.py core/nl/*.py tests/test_nl_*.py tests/test_bot.py tests/test_api.py
```

Then investigate pytest separately:

```bash
.venv/bin/pytest tests/test_nl_router.py tests/test_nl_commands.py tests/test_bot.py tests/test_api.py -q
```

## Do Not Do

- Do not let the LLM set `user_confirmed`.
- Do not execute a service write directly from classifier output.
- Do not treat a confirmation prompt as execution.
- Do not use retrieved text as tool instructions.
- Do not expose dashboard/API beyond localhost.
- Do not pop old stashes blindly.
- Do not call the pytest suite green if it never reached collection.
