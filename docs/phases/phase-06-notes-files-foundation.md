# Phase 6 — Notes + Files Foundation

## Status

Planned / next backend foundation.

## Goal

Add a local-first knowledge substrate.

Atenas should support:

- manual study notes
- file metadata registry
- links between notes and files
- links to modules and assignments
- simple deterministic keyword search
- Telegram commands for notes/files/search
- read-only dashboard pages

## Product question

```text
What notes and files do I have for this module, assignment, or topic?
```

## In scope

### Notes

- create note
- update note
- list notes
- view note detail
- archive note
- link note to module/assignment/file
- tags
- source type

### Files

- register file metadata
- derive filename/path/type
- optional size/hash if file exists
- archive file metadata
- link file to module/assignment/note
- tags

### Search

Simple deterministic keyword search over:

- note title
- note body
- note tags
- file title
- filename
- path
- description
- file tags

## Out of scope

Do not add:

- RAG
- embeddings
- vector DB
- PDF extraction
- OCR
- LLM summaries
- cloud APIs
- Obsidian sync
- iCloud/Drive sync
- file watcher
- dashboard write forms

## Preferred architecture

```text
core/knowledge/
  models.py
  repository.py
  service.py
  validators.py
  search.py
```

Dependency direction:

```text
Telegram -> KnowledgeService -> KnowledgeRepository
Dashboard -> KnowledgeService -> KnowledgeRepository
KnowledgeService -> AcademicRepository only for module/assignment validation
```

## Schema

Tables:

- `notes`
- `files`
- `note_file_links`

### notes

Fields:

```text
id
title
body
module_id nullable
assignment_id nullable
file_id nullable
source_type default manual
tags nullable
archived default 0
created_at
updated_at
```

### files

Fields:

```text
id
path
filename
title nullable
description nullable
module_id nullable
assignment_id nullable
file_type nullable
mime_type nullable
size_bytes nullable
sha256 nullable
tags nullable
archived default 0
created_at
updated_at
```

### note_file_links

Fields:

```text
id
note_id
file_id
created_at
UNIQUE(note_id, file_id)
```

## Telegram commands

Required:

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

## Dashboard routes

Read-only:

```text
/dashboard/notes
/dashboard/files
/dashboard/search
```

## Tests

Add tests for:

- repository CRUD/archive/link
- service validation
- tag normalization
- module/assignment validation
- missing file handling
- search behavior
- Telegram commands
- dashboard pages

## Exit criteria

Phase 6 is complete when Atenas can store, link, list, archive, and search notes/file metadata.
