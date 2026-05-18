# Atenas Handoff — Natural Language Interface

## Date

2026-05-18

## Project identity

Name: Atenas
Repo: `NathanLCR/atenas`
Language: Python 3.11
Stack: FastAPI · python-telegram-bot 21.6 · SQLite · Ollama (local LLM)

Atenas is a local-first AI study operating system for a working student.
The primary user interface is a Telegram bot. All data is local — SQLite,
no cloud services except an optional cloud LLM that is disabled by default.

---

## Repository state

- Branch to work from: `main`
- HEAD: `70a3eaf` (fix: LLM status mock)
- All tests passing: **383 passed**

```bash
git clone https://github.com/NathanLCR/atenas
cd atenas
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q          # must pass before you start
```

---

## What is already built (do not rebuild)

| Phase | What exists |
|---|---|
| 0–1 | FastAPI app, SQLite schema, config, JSONL logging, skill registry, policy engine |
| 2 | Telegram bot with allowlist, dashboard (read-only) |
| 3 | Work shifts, class sessions, academic availability |
| 4 | Deterministic study planner |
| 5 | Controlled data input (add/edit assignments, modules, shifts) |
| 6 | Notes + files + keyword search |
| 6.5 | Developer code map in `docs/code-map/` |
| 7 | Local Ollama LLM over selected notes (summarise, explain, flashcards, etc.) |
| 8 | Controlled RAG: retrieval over notes/files, explicit source IDs, `/ask_notes` |
| 9 | Notifications + reminders (asyncio background loops, `/reminders` command) |

**The bot has 38 slash commands.** They all work. Do not change their
behaviour — only add on top of them.

---

## Current Telegram command surface (reference)

**Status / info**
`/ping` `/status` `/skills` `/reminders`

**Schedule / planning**
`/today` `/week` `/deadlines` `/availability` `/plan` `/study`

**Data input (write)**
`/add_module` `/add_class` `/add_shift` `/add_assignment`
`/set_status` `/set_hours`

**Data listing (read)**
`/modules` `/classes` `/shifts` `/assignments`

**Notes / files**
`/add_note` `/notes` `/note` `/archive_note`
`/add_file` `/files` `/search` `/link_note_file`

**Local LLM over a note**
`/summarize_note` `/explain_note` `/questions_note`
`/flashcards_note` `/rewrite_note`

**RAG retrieval**
`/ask_notes` `/ask_note` `/sources`

---

## Key files

| File | Purpose |
|---|---|
| `app/bot.py` | All Telegram command handlers (~1430 lines) |
| `app/main.py` | FastAPI app factory + lifespan |
| `app/config.py` | Settings loaded from `.env` |
| `app/dashboard.py` | Read-only dashboard routes |
| `core/academic/service.py` | Schedule, planning, CRUD |
| `core/knowledge/service.py` | Notes, files, keyword search |
| `core/llm/service.py` | Local Ollama note actions |
| `core/llm/client.py` | Raw Ollama HTTP client (stdlib only) |
| `core/retrieval/service.py` | RAG over registered notes/files |
| `core/notifications/service.py` | Notification logic (deadlines, study blocks) |
| `core/db.py` | SQLite schema + connection helper |
| `skills/status/handler.py` | `/status`, `/ping`, `/skills` logic |
| `docs/code-map/` | Architecture diagrams for each module |

---

## What to build next — Natural Language Interface

**Goal:** the user can send plain-text messages to the bot and get useful
responses without knowing slash commands.

Examples that must work after this phase:

```
"what's my plan for today?"          → same output as /today
"add an assignment: ML exam Friday"  → parse and confirm before inserting
"how many study hours do I have?"    → /availability output
"what do my notes say about CNNs?"  → /ask_notes q="CNNs"
"summarise note 5"                   → /summarize_note 5
```

**Read the phase spec before starting:**
`docs/phases/phase-natural-language-interface.md`

### Architecture summary (from the spec)

Create `core/nl/` with four files:

```
core/nl/
  intent.py      # IntentMatch dataclass + intent name constants
  classifier.py  # NLClassifier: sends text to Ollama, parses JSON intent+slots
  slots.py       # extract_slots(): normalise date strings, priority labels, etc.
  router.py      # NLRouter: maps IntentMatch -> existing service/command call
  prompts.py     # classification prompt template
```

In `app/bot.py`, add one new handler:

```python
async def natural_language_handler(update, context):
    ...
```

Register it with `MessageHandler(filters.TEXT & ~filters.COMMAND & allowlist_filter, ...)`.
This means it fires only on plain-text messages that are NOT slash commands.

### Classification

Use `core/llm/client.py` (the existing `OllamaClient`) to classify intent.
Return JSON: `{"intent": "...", "confidence": 0.85, "slots": {...}}`.

If Ollama is unavailable → return a generic fallback message, do not crash.
If confidence < 0.7 → reply with the closest slash command suggestion.

### Write intents need confirmation

Any intent that creates or modifies data (add assignment, set status, add note)
MUST show parsed values and wait for "yes" / "no" before calling the service.
Use `context.user_data` to hold pending confirmations per user.

### Fallback intent

If nothing matches → route to `/ask_notes` with the original text as query.
This turns any unrecognised message into a RAG search over the user's notes.

---

## Hard constraints (do not violate)

1. **All 383 existing tests must still pass** after this phase.
2. All 38 slash commands must still work unchanged.
3. No new external dependencies unless absolutely necessary.
4. No cloud LLM calls. Classification uses the local Ollama instance only.
5. If Ollama is offline, natural language handling degrades gracefully —
   it does NOT block slash commands.
6. Write operations require explicit user confirmation in the chat.
7. The Telegram allowlist (`TELEGRAM_ALLOWED_USER_IDS`) still applies to
   all messages, including natural language ones.
8. No autonomous actions — the bot never initiates a data change without
   the user confirming.

---

## Environment

```bash
# Required: Ollama running locally with a model loaded
ollama pull llama3.1:8b
ollama serve

# Start Atenas
.venv/bin/uvicorn app.main:app --reload

# Run tests
.venv/bin/pytest -q
```

`.env` file (minimum to run with Telegram):

```env
TELEGRAM_BOT_TOKEN=<your token>
TELEGRAM_ALLOWED_USER_IDS=<your Telegram user ID>
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Testing rule

Mock Ollama responses in tests. Do not call a real model in the test suite.
Pattern: `patch("core.nl.classifier.OllamaClient")` returning a fixed JSON string.

New tests go in:
- `tests/test_nl_classifier.py` — intent classification logic
- `tests/test_nl_router.py` — routing to existing handlers
- `tests/test_nl_commands.py` — Telegram handler integration

---

## Definition of done

The phase is complete when:

1. `pytest -q` shows ≥ 383 passed (the current baseline) plus new NL tests.
2. Sending "what's my schedule today?" in Telegram returns the same content as `/today`.
3. Sending "add assignment ML exam due Friday" shows a confirmation message with parsed fields.
4. Sending "what do my notes say about transformers?" returns a RAG answer with sources.
5. All existing slash commands pass their existing tests unchanged.

---

## Docs to read first

1. `docs/phases/phase-natural-language-interface.md` — full spec
2. `docs/code-map/telegram.md` — how the bot is structured
3. `docs/code-map/core-knowledge.md` — note/file data model
4. `docs/AGENT_POLICY.md` — what the agent is and is not allowed to do
5. `docs/codex/MASTER_CODEX_HANDOFF.md` — full project history
