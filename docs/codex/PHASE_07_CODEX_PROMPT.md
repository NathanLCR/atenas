# Codex Prompt — Atenas Phase 7

You are working on the `atenas-core` repo.

## Required baseline

Phase 6 must be complete.

Required:

- notes/files foundation
- knowledge service/repository/search
- Telegram note/file/search commands
- dashboard notes/files/search pages

## Task

Implement Phase 7: Local LLM Assistance over Selected Notes.

Read:

```text
docs/phases/phase-07-local-llm-selected-notes.md
```

## Goal

Allow controlled local LLM actions on explicit note IDs.

Examples:

```text
/summarize_note 12
/explain_note 12
/questions_note 12
/flashcards_note 12
/rewrite_note 12 style=concise
```

## Hard constraints

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

## Preferred provider

Ollama-compatible local endpoint.

Default settings:

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

## Tests

Mock HTTP/LLM calls.

Do not require Ollama during tests.

## Acceptance criteria

- selected note only
- local LLM unavailable handled cleanly
- tests pass
- no RAG/embeddings/cloud/agent features
