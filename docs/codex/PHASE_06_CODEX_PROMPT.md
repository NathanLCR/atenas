# Codex Prompt — Atenas Phase 6

You are working on the `atenas-core` repo.

## Current status

Atenas has completed Phases 1–5.

Latest known baseline:

```text
python3 -m pytest
264 passed
0 failed
```

Phase 5 added controlled deterministic input/editing, imports, Telegram data commands, and `/dashboard/data`.

## Task

Implement Phase 6: Notes + Files Foundation.

Read:

```text
docs/phases/phase-06-notes-files-foundation.md
```

## Goal

Add a local-first knowledge substrate:

- manual notes
- file metadata registry
- note-file links
- module/assignment links
- deterministic keyword search
- Telegram commands
- read-only dashboard pages

## Hard constraints

Do not add:

- LLM
- RAG
- embeddings
- vector DB
- PDF parsing
- OCR
- cloud APIs
- Obsidian sync
- iCloud/Drive sync
- dashboard write forms
- unnecessary dependencies

## Preferred architecture

```text
core/knowledge/
  models.py
  repository.py
  service.py
  validators.py
  search.py
```

## Required Telegram commands

```text
/add_note
/notes
/note
/archive_note
/add_file
/files
/search
```

Optional:

```text
/link_note_file
```

## Required dashboard routes

```text
/dashboard/notes
/dashboard/files
/dashboard/search
```

Read-only only.

## Required tests

Add tests for:

- repository CRUD/archive/link
- service validation
- search
- Telegram commands
- dashboard routes
- regressions

## Acceptance criteria

- existing tests still pass
- new tests pass
- no out-of-scope features added
- dashboard remains read-only
