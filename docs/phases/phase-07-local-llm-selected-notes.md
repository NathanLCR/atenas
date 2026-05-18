# Phase 7 — Local LLM Assistance over Selected Notes

## Status

Planned.

## Required baseline

Phase 6 must be complete first.

Required:

- notes
- files
- note/file links
- knowledge service
- simple search
- Telegram note/file commands
- dashboard notes/files/search

## Goal

Add local LLM actions over explicitly selected notes.

This is not RAG yet.

Atenas should answer:

```text
Can you summarize this note?
Can you explain this note?
Can you generate study questions from this note?
Can you rewrite this note?
```

## Core rule

The user must explicitly select the note.

Example:

```text
/summarize_note 12
```

Do not process all notes automatically.

## In scope

- local Ollama-compatible LLM client
- summarize selected note
- explain selected note
- generate study questions from selected note
- generate flashcards from selected note
- rewrite selected note
- LLM call metadata logging
- Telegram commands
- optional read-only dashboard for LLM logs

## Out of scope

Do not add:

- RAG
- embeddings
- vector DB
- PDF parsing
- OCR
- cloud fallback
- autonomous agents
- web search
- automatic processing of all notes

## Suggested config

```text
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
LLM_TIMEOUT_SECONDS=60
```

## Preferred architecture

```text
core/llm/
  client.py
  prompts.py
  service.py
  models.py
```

Dependency direction:

```text
Telegram -> LLMService -> KnowledgeService -> KnowledgeRepository
LLMService -> LLMClient
```

`core/knowledge` must not depend on `core/llm`.

## Telegram commands

```text
/summarize_note
/explain_note
/questions_note
/flashcards_note
/rewrite_note
```

Examples:

```text
/summarize_note 12
/explain_note 12
/questions_note 12
/flashcards_note 12
/rewrite_note 12 style=concise
```

## Prompt policy

- use only selected note content
- do not invent citations
- do not modify the database unless explicitly requested in a later phase
- keep Telegram output compact
- handle local LLM unavailable cleanly

## Tests

Mock the LLM client.

Test:

- client success
- client failure
- timeout/malformed response
- service uses selected note only
- missing note
- Telegram commands
- allowlist behavior
- dashboard LLM logs if implemented

## Exit criteria

Phase 7 is complete when local LLM actions work over explicit note IDs, with mocked tests and clean failure handling.
