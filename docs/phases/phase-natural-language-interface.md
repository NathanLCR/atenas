# Phase: Natural Language Interface

## Status

Next phase.

## Goal

Allow the user to send plain-text messages to Atenas on Telegram and get
useful responses — without needing to know slash-command syntax.

The user should be able to write:

```
what's my schedule today?
add an assignment: NLP Essay due Friday at 5pm, priority high
how many hours do I have to study this week?
summarise note 3
what do my notes say about attention mechanisms?
```

And Atenas should understand, route to the right handler, and reply.

## Product question

```text
Can I use Atenas by just talking to it naturally?
```

## In scope

- Plain-text message handler that routes to existing command logic
- Intent classification using local Ollama (same model already in use)
- Slot extraction for structured commands (date, title, priority, module)
- Fallback to RAG (`/ask_notes`) when no intent matches
- Confidence threshold: if intent is unclear, ask the user to clarify or
  suggest the right slash command
- Read-only intents first (status, schedule, plan, deadlines, availability)
- Write intents second (add assignment, set status, add note) with explicit
  confirmation before mutation

## Out of scope

- Autonomous multi-turn planning sessions
- Web search or internet retrieval
- Cloud LLM fallback for NL understanding
- Replacing slash commands (they stay and remain the primary interface)
- Anything that creates, edits, or deletes data without user confirmation

## Suggested Telegram commands to preserve (do not remove)

All existing slash commands must keep working. Natural language is an
additive layer on top, not a replacement.

## Architecture

```text
core/nl/
  intent.py        # IntentMatch dataclass, intent registry
  classifier.py    # NLClassifier: prompt -> IntentMatch via Ollama
  slots.py         # extract_slots(): parse date/priority/title from text
  router.py        # NLRouter: IntentMatch -> existing service call
  prompts.py       # prompt templates for classification and slot extraction
```

Key design rules:

1. The NL layer is a thin translation layer. It maps natural language to
   existing service calls — it does NOT reimplement scheduling, planning,
   or retrieval logic.
2. Classification uses the local Ollama model. If Ollama is unavailable,
   fall back to: "I could not process that. Try /status or /help."
3. Write intents (add, update, delete) MUST show the parsed slot values
   and ask for confirmation before calling the service. Example:
   ```
   I understood: add assignment "NLP Essay" due 2026-05-22 17:00,
   priority high, module: NLP
   Confirm? (yes / no)
   ```
4. Confidence threshold: if the classifier returns confidence < 0.7,
   reply with the closest slash command suggestion rather than guessing.
5. No multi-turn state for now — each message is processed independently.

## Intent map (first implementation)

| Natural intent | Routes to |
|---|---|
| "what's my schedule / today / plan" | `today_command` |
| "show my week / weekly schedule" | `week_command` |
| "what are my deadlines" | `deadlines_command` |
| "how available am I / study time" | `availability_command` |
| "give me a study plan" | `plan_command` |
| "what should I study now / next" | `study_command` |
| "add assignment <...>" | `add_assignment_command` (with confirmation) |
| "set assignment status / mark done" | `set_status_command` (with confirmation) |
| "list my assignments / modules / shifts" | `assignments_command` / `modules_command` |
| "add note <...>" | `add_note_command` (with confirmation) |
| "summarise / explain note <n>" | `summarize_note_command` / `explain_note_command` |
| "what do my notes say about <topic>" | `ask_notes_command` |
| fallback (no match) | `ask_notes_command` with original text as query |

## Classifier prompt design

Classify the user's message into one of the intents. Return JSON only:

```json
{"intent": "<name>", "confidence": 0.0-1.0, "slots": {...}}
```

Slots to extract per intent (examples):
- add_assignment: `{title, due_at, priority, module, estimated_hours}`
- set_status: `{assignment_id_or_title, status}`
- add_note: `{title, content}`
- note_action: `{note_id_or_title, action}`
- ask_notes: `{query, module}`

## Confirmation flow for write intents

```
user: add assignment linear algebra exam due next monday 9am
bot:  Add assignment?
      Title: Linear Algebra Exam
      Due: 2026-05-25 09:00
      Priority: normal (inferred)
      Module: not specified
      Reply "yes" to confirm or "no" to cancel.
user: yes
bot:  ✅ Assignment added: Linear Algebra Exam (due Mon 09:00)
```

## Tests

Test with mock Ollama responses. Do not call a real LLM in tests.

Test:
- Intent classification returns correct intent and slots
- Confidence below threshold returns clarification message
- Read intents route to correct service without confirmation
- Write intents trigger confirmation message before service call
- Confirmation "yes" executes the service call
- Confirmation "no" cancels without side effects
- Ollama unavailable returns graceful fallback
- Non-command Telegram message is handled (not silently dropped)

## Exit criteria

Phase is complete when the user can:
1. Send a plain-text message and get a useful response
2. Add an assignment, note, or check schedule in natural language
3. All existing slash commands still pass all existing tests
