# Atenas — Schemas v0.1

All LLM outputs must conform to a Pydantic model before any action is taken. This file defines the canonical schemas.

Corrections applied from PDF audit:
- WorkShiftsExtracted: array wrapper + needs_confirmation (from PDF).
- MemoryItemExtracted: should_store, domain, importance, summary (from PDF).
- DailyPlanGenerated: capacity, reason per block, warnings (from PDF).

---

## Schema Conventions

- All Pydantic models reject undeclared fields via `model_config = ConfigDict(extra="forbid")` (emitted as JSON Schema `additionalProperties: false`). Implemented as the shared `StrictModel` base.
- Enum values are lowercase strings.
- Timestamps are ISO 8601 strings, UTC. Wall-clock fields (`start_time`,
  `end_time`, `date`) are interpreted in `settings.timezone`, not UTC.
- Every `confidence` field is **model self-reported and uncalibrated** — it
  is a weak hint, not a probability. `MIN_CONFIDENCE_THRESHOLD` (0.65) is the
  *secondary* escalation signal only. The *primary*, reliable signals are
  schema-validity and explicit task class (see AGENT_POLICY "LLM Provider
  Rules"). Never make a safety or correctness decision on `confidence` alone.

---

## Work Schedule — LLM Output

### `WorkShiftsExtracted` (array wrapper)

From PDF spec. Supports multiple shifts from one message.

```json
{
  "shifts": [
    {
      "workplace": "The Anchor",
      "date": "2024-11-05",
      "start_time": "18:00",
      "end_time": "23:30",
      "role": null,
      "commute_minutes": 25,
      "fatigue_level": "high",
      "notes": null,
      "confidence": 0.92
    }
  ],
  "needs_confirmation": false
}
```

Fields per shift:
- `workplace`: string | null
- `date`: YYYY-MM-DD string | null (null if ambiguous — triggers needs_confirmation)
- `start_time`: HH:MM string (required)
- `end_time`: HH:MM string (required)
- `role`: string | null
- `commute_minutes`: integer | null (0-300)
- `fatigue_level`: enum `low`, `medium`, `high` (default: medium)
- `notes`: string | null
- `confidence`: float 0.0-1.0 (required)

Top-level:
- `shifts`: array of shift objects (required)
- `needs_confirmation`: boolean (required)

---

## Class Timetable — LLM Output

### `ClassSessionsExtracted` (array wrapper)

Mirrors `WorkShiftsExtracted`. Supports multiple class sessions from one
message. Class sessions are hard scheduling blocks (FR-05).

```json
{
  "sessions": [
    {
      "module_id": "CS7045",
      "title": "AI in Education — Lecture",
      "date": "2024-11-05",
      "start_time": "14:00",
      "end_time": "16:00",
      "location": "Room B12",
      "recurrence": "weekly",
      "confidence": 0.9
    }
  ],
  "needs_confirmation": false
}
```

Fields per session:
- `module_id`: string | null
- `title`: string (required)
- `date`: YYYY-MM-DD string | null (null if ambiguous → needs_confirmation)
- `start_time`: HH:MM string (required)
- `end_time`: HH:MM string (required)
- `location`: string | null
- `recurrence`: string | null (e.g. `weekly`; null = one-off)
- `confidence`: float 0.0-1.0 (required)

Top-level:
- `sessions`: array of session objects (required)
- `needs_confirmation`: boolean (required)

---

## Memory — LLM Output

### `MemoryItemExtracted` (from PDF spec)

```json
{
  "should_store": true,
  "domain": "studies",
  "topic": "dissertation",
  "summary": "Dissertation topic is AI safety in education",
  "importance": "high",
  "sensitive": false,
  "tags": ["dissertation", "ai", "education"],
  "confidence": 0.88
}
```

Fields:
- `should_store`: boolean — LLM can decline to store noise (required)
- `domain`: enum `studies`, `work`, `assignments`, `papers`, `projects`, `preferences`, `archive` (required)
- `topic`: string max 100 chars (required)
- `summary`: string max 2000 chars (required)
- `importance`: enum `low`, `medium`, `high`, `critical` (required)
- `sensitive`: boolean (default false) — true marks the item as private
  (health, finances, relationships, credentials, anything the user would not
  want sent off-device). The cloud gate (AGENT_POLICY "Memory and Notes" and
  "LLM Provider Rules") MUST refuse to send a `sensitive` item to a cloud LLM
  without explicit per-use confirmation. This is the implementation hook for
  that rule; external providers are not wired in v1, so the gate is a target
  contract for whichever change first enables them.
- `tags`: array of strings, max 8 items
- `confidence`: float 0.0-1.0 (required, self-reported — see Conventions)

---

## Study Planner — I/O

**Design rule:** code authors every time; the LLM never does. The LLM is
given code-authored slots and returns assignments keyed by `slot_id`. The
output schema has no LLM-writable time field, so a hallucinated time is
structurally impossible (it would fail `extra="forbid"`).

### `AvailabilitySlot` (code-authored — LLM input, never LLM output)

Computed by the deterministic Availability Algorithm (see REQUIREMENTS.md FR-06).

```json
{
  "slot_id": 0,
  "date": "2024-11-06",
  "start_time": "10:00",
  "end_time": "12:30",
  "max_intensity": "deep"
}
```

Fields:
- `slot_id`: integer ≥ 0 (required) — stable index the LLM references
- `date`: YYYY-MM-DD string (required)
- `start_time`: HH:MM string (required) — wall-clock in `settings.timezone`
- `end_time`: HH:MM string (required)
- `max_intensity`: enum `recovery`, `light`, `medium`, `deep` (required) —
  the fatigue cap; assignments may not exceed it

### `DailyPlanGenerated` (LLM output)

```json
{
  "date": "2024-11-06",
  "capacity": "medium",
  "assignments": [
    {
      "slot_id": 0,
      "title": "Write literature review section 1 — CS7045",
      "task_type": "writing",
      "task_id": "e5f6g7h8-...",
      "intensity": "deep",
      "reason": "Highest deadline risk; slot cap allows deep work."
    }
  ],
  "warnings": [
    "Deadline CS7045 within 72h — elevated priority."
  ]
}
```

Fields:
- `date`: YYYY-MM-DD string (required)
- `capacity`: enum `low`, `medium`, `high` (required)
- `assignments`: array of `BlockAssignment` (required, may be empty)
  - `slot_id`: integer ≥ 0 (required) — MUST reference an input slot;
    code rejects unknown ids
  - `title`: string (required)
  - `task_type`: string | null
  - `task_id`: string | null — links the block to a stored task
  - `intensity`: enum `recovery`, `light`, `medium`, `deep` (required) —
    code rejects/clamps any value exceeding the slot's `max_intensity`
  - `reason`: string (required)
- `warnings`: array of strings (required, may be empty)
- **No time fields.** Final block times are joined in from the referenced
  `AvailabilitySlot` by code.

---

## Paper Metadata — LLM Output

### `PaperMetadataExtracted`

```json
{
  "title": "ALCE: A Large-scale Citation Evaluation Benchmark",
  "authors": ["Tianyu Gao", "Howard Yen"],
  "year": 2023,
  "abstract": "We introduce ALCE, a benchmark...",
  "keywords": ["citation", "evaluation", "NLP"],
  "confidence": 0.95
}
```

Fields:
- `title`: string max 500 chars (required)
- `authors`: array of strings, min 1 (required)
- `year`: integer 1900-2100 | null (required)
- `abstract`: string max 5000 chars (required)
- `keywords`: array of strings, max 20
- `confidence`: float 0.0-1.0 (required)

---

## Literature Matrix — LLM Output

### `LiteratureMatrixEntry`

```json
{
  "paper_id": "abc123",
  "research_question": "How can citation grounding be evaluated at scale?",
  "methodology": "Benchmark evaluation with automatic metrics",
  "sample": "3 datasets, 8 LLMs",
  "key_findings": "LLMs struggle with precise citation generation...",
  "limitations": "Limited to English-language papers",
  "relevance_to_topic": "Directly supports dissertation chapter 3",
  "confidence": 0.85
}
```

Fields:
- `paper_id`: string (required)
- `research_question`: string (required)
- `methodology`: string (required)
- `sample`: string | null (required)
- `key_findings`: string (required)
- `limitations`: string (required)
- `relevance_to_topic`: string | null (required)
- `confidence`: float 0.0-1.0 (required)

---

## Flashcard — LLM Output

### `FlashcardSetGenerated`

```json
{
  "topic": "Recommender Systems",
  "cards": [
    {
      "question": "What is collaborative filtering?",
      "answer": "A technique that predicts user preferences based on similar users' choices."
    }
  ]
}
```

---

## Action System

### `ActionProposal`

Every LLM-generated action must be wrapped in this before the policy engine evaluates it.

```json
{
  "action_type": "write_memory",
  "payload": { "...": "..." },
  "confidence": 0.88,
  "reason": "Storing new memory item from user input."
}
```

Fields:
- `action_type`: string (required) — the policy engine is an **allowlist**:
  `action_type` must be in `ALLOWED_ACTIONS` (or `CONFIRMATION_REQUIRED`
  with confirmation). Anything else — including a novel string the model
  invents — is **blocked by default-deny**. The LLM cannot route around
  policy by renaming an action.
- `payload`: object (required)
- `confidence`: float 0.0-1.0 (required, self-reported — see Conventions)
- `user_confirmed`: boolean, **default `false`** (the safe default; the
  field is omitted by the LLM and set True by *code* only after the user
  explicitly confirms, e.g. replies `yes` / `/confirm`). For an action in
  `CONFIRMATION_REQUIRED`, `false` → blocked with `NEEDS_CONFIRMATION`;
  `true` → allowed. It can never turn a forbidden or unknown action into an
  allowed one. (Renamed from the old `requires_confirmation`, whose name
  inverted the safe default and was a confirmation-bypass footgun.)
- `reason`: string | null
