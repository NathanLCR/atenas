# Atenas — Schemas v0.1

All LLM outputs must conform to a Pydantic model before any action is taken. This file defines the canonical schemas.

Corrections applied from PDF audit:
- WorkShiftsExtracted: array wrapper + needs_confirmation (from PDF).
- MemoryItemExtracted: should_store, domain, importance, summary (from PDF).
- DailyPlanGenerated: capacity, reason per block, warnings (from PDF).

---

## Schema Conventions

- All Pydantic models use `additionalProperties = False` (via model_config).
- Enum values are lowercase strings.
- Timestamps are ISO 8601 strings.
- Confidence threshold is 0.65 everywhere (from config.MIN_CONFIDENCE_THRESHOLD).

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

## Memory — LLM Output

### `MemoryItemExtracted` (from PDF spec)

```json
{
  "should_store": true,
  "domain": "studies",
  "topic": "dissertation",
  "summary": "Dissertation topic is AI safety in education",
  "importance": "high",
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
- `tags`: array of strings, max 8 items
- `confidence`: float 0.0-1.0 (required)

---

## Study Planner — LLM Output

### `DailyPlanGenerated` (from PDF spec)

```json
{
  "date": "2024-11-06",
  "capacity": "medium",
  "blocks": [
    {
      "start_time": "09:00",
      "end_time": "10:00",
      "title": "Review flashcards — CS7012",
      "task_type": "revision",
      "intensity": "recovery",
      "reason": "Late shift yesterday ended 23:30. Recovery only before 10:00."
    },
    {
      "start_time": "10:00",
      "end_time": "12:30",
      "title": "Write literature review section 1 — CS7045",
      "task_type": "writing",
      "intensity": "deep",
      "reason": "Deadline in 4 days. Deep work slot available."
    }
  ],
  "warnings": [
    "Deadline CS7045 within 72h — elevated priority.",
    "Late shift yesterday — no deep work before 10:00."
  ]
}
```

Fields:
- `date`: YYYY-MM-DD string (required)
- `capacity`: enum `low`, `medium`, `high` (required)
- `blocks`: array of block objects (required)
  - `start_time`: HH:MM string | null
  - `end_time`: HH:MM string | null
  - `title`: string (required)
  - `task_type`: string | null
  - `intensity`: enum `recovery`, `light`, `medium`, `deep` (required)
  - `reason`: string — why this block was scheduled this way (required)
- `warnings`: array of strings (required, may be empty)

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
  "requires_confirmation": false,
  "reason": "Storing new memory item from user input."
}
```

Fields:
- `action_type`: string (required) — must match a registered handler or a policy set entry
- `payload`: object (required)
- `confidence`: float 0.0-1.0 (required)
- `requires_confirmation`: boolean — true means user already confirmed (required)
- `reason`: string | null
