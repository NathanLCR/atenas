# Phase 8 — Controlled Retrieval/RAG Foundation

## Status

Planned MVP final phase.

## Required baseline

Phase 6 and Phase 7 should be complete.

Required:

- notes/files foundation
- local LLM client
- explicit note actions
- simple keyword search
- stable data model

## Goal

Add controlled retrieval over notes/files with clear source display.

This is the first RAG phase.

## Product question

```text
What do my notes/files say about this topic, and which sources support the answer?
```

## In scope

- chunk selected notes and optionally text files
- local embeddings
- local vector store or SQLite-friendly retrieval strategy
- retrieval over notes/file text only
- answer generation with source references
- citation/source display
- Telegram command for controlled question answering
- dashboard read-only retrieval view if useful

## Out of scope

Do not add:

- autonomous agents
- web search
- uncontrolled internet retrieval
- automatic ingestion of entire filesystem
- OCR
- complex PDF parsing unless explicitly scoped
- cloud fallback
- multi-user deployment
- production-grade evaluation

## Suggested commands

```text
/ask_notes q="transformers attention" module=2
/ask_note note=12 q="what is the main idea?"
/sources q="citation grounding"
```

## Retrieval rules

- only search registered notes/files
- exclude archived items
- display source IDs
- keep answers bounded
- do not claim unsupported information
- prefer "not enough information" when retrieval is weak

## Suggested architecture

```text
core/retrieval/
  chunking.py
  embeddings.py
  vector_store.py
  service.py
  models.py
```

## Safety/evaluation rule

RAG must show sources.

If no useful source is retrieved, answer:

```text
I do not have enough information in your registered notes/files to answer this.
```

## Tests

Mock embeddings/LLM when possible.

Test:

- chunking
- indexing
- retrieval
- archived exclusion
- source display
- no-source fallback
- Telegram commands
- deterministic behavior where applicable

## Exit criteria

Phase 8 is complete when Atenas can answer questions over registered notes/files with explicit sources.
