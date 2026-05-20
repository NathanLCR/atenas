# Atenas Handoff - 2026-05-20

## Status

This handoff reflects the documentation refactor after the Atenas Core code
review. It is not a verified implementation baseline.

The product direction is now:

```text
local-running app + Telegram-first governed LLM tool agent
```

Dashboard and REST API are local support surfaces. Telegram remains the main
interface.

The governing doctrine is:

```text
LLM proposes.
Deterministic systems validate.
Human approves critical actions.
```

## Verification

Do not rely on old test counts from historical docs. The latest review attempt
reported that `.venv/bin/pytest -q` and even importing `pytest` hung locally.

Before implementation work:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

If pytest still hangs, debug the environment before treating the suite as a
valid baseline.

## Current Product Contract

- Single-user, local-running assistant.
- Telegram is the primary user interface.
- Plain Telegram messages should route to an LLM agent with Atenas tools.
- Slash commands remain deterministic shortcuts.
- Local dashboard/API must bind to localhost and are not remote product
  surfaces.
- Local Ollama is the default LLM provider.
- External LLM providers are opt-in data egress.
- Telegram allowlist is mandatory.
- LLM-originated writes require proposal, deterministic validation, human
  confirmation, policy approval, service execution, and audit logging.
- Critical actions include all LLM-originated writes in v1, destructive
  changes, external communication, configuration changes, sensitive data
  egress, and ambiguous target resolution.

Read these docs first:

1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/SECURITY.md`
4. `docs/AGENT_POLICY.md`
5. `docs/REQUIREMENTS.md`
6. `docs/HANDOFF_NL_INTERFACE.md`
7. `docs/HANDOFF_PROPOSE_VALIDATE_APPROVE.md`

## Existing Telegram Surface to Preserve

Status:

- `/ping`
- `/status`
- `/skills`
- `/reminders`

Schedule/planning:

- `/today`
- `/week`
- `/deadlines`
- `/availability`
- `/plan`
- `/study`

Controlled data input/editing:

- `/add_module`
- `/add_class`
- `/add_shift`
- `/add_assignment`
- `/set_status`
- `/set_hours`
- `/modules`
- `/classes`
- `/shifts`
- `/assignments`

Knowledge:

- `/add_note`
- `/notes`
- `/note`
- `/archive_note`
- `/add_file`
- `/files`
- `/search`
- `/link_note_file`

Selected-note local LLM:

- `/summarize_note`
- `/explain_note`
- `/questions_note`
- `/flashcards_note`
- `/rewrite_note`

Retrieval:

- `/ask_notes`
- `/ask_note`
- `/sources`

## Next Implementation Target

Implement the Telegram LLM tool interface described in
`docs/HANDOFF_NL_INTERFACE.md` and
`docs/phases/phase-natural-language-interface.md`.

The core flow should be:

```text
Telegram user
  -> allowlist auth
  -> LLM agent
  -> Atenas tool registry
  -> core services
  -> structured result
  -> Telegram reply
```

Write flow:

```text
Telegram user
  -> LLM proposes write
  -> deterministic validation and ID resolution
  -> confirmation prompt
  -> policy check
  -> service execution
  -> audit log
```

## Review-Driven Fix Targets

These are implementation issues discovered in review and reflected in the new
docs. They are not fixed by this docs-only pass.

- Dashboard/API should be localhost-only by default.
- Docker publishing should bind to localhost only.
- Empty Telegram allowlist should fail startup when Telegram is enabled.
- REST endpoints must not use fake `user_id=0` actor semantics.
- LLM/NL writes must not bypass the policy engine.
- Dead/fake LLM telemetry modules should be removed or quarantined.
- Retrieval should not rebuild the entire chunks table on every query.
- `core/` should not import `app.config`; inject settings instead.
- Prompt templates should delimit untrusted input.
- Tests should use isolated settings/database fixtures.

## Useful Commands

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload
docker-compose up
```

For local web access, use `http://127.0.0.1:8000`.
