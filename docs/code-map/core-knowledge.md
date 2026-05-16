# Core Knowledge — Notes, Files, Search (Phase 6)

## Purpose

Local-first knowledge layer for study notes, file metadata registry, note-file linking, and deterministic keyword search.

## Files

| File | Role |
|------|------|
| `core/knowledge/models.py` | Pydantic models: Note, FileRecord, NoteFileLink, SearchResult |
| `core/knowledge/repository.py` | SQLite CRUD for notes, files, note_file_links |
| `core/knowledge/service.py` | Business logic, validation, module/assignment checks |
| `core/knowledge/validators.py` | Tag normalization, file type/mime derivation, field validation |
| `core/knowledge/search.py` | SQL LIKE search engine with deterministic ranking |

## Main classes

- `KnowledgeService` — primary entry point for knowledge operations.
- `KnowledgeRepository` — SQLite persistence for knowledge tables.
- `SearchEngine` — keyword search over notes and file metadata.
- `Note`, `FileRecord`, `SearchResult` — Pydantic models.

## Data flow

```text
/add_note → parse_kv_args → KnowledgeService.create_note() → validate → Repository → CommandResult
/search → KnowledgeService.search() → SearchEngine.search() → SQL LIKE → ranked results
```

## Important constraints

- Note/file IDs are INTEGER AUTOINCREMENT (different from academic UUID4 TEXT IDs).
- Tags stored as comma-separated lowercase hyphenated strings.
- Soft archive (`archived=1`); excluded from normal listing and search.
- File registration rejects missing paths by default (`allow_missing=False`).
- Duplicate file detection by normalized path.
- Search uses SQL LIKE only — no embeddings, no vector DB.

## Ranking (search)

1. Exact title match → 100
2. Title contains query → 80
3. Tag contains query → 60
4. Body/description/path contains query → 40
5. Ordered by `updated_at DESC`

## Pitfalls

- Do not mix knowledge INTEGER IDs with academic TEXT UUID IDs.
- `find_duplicate_file` checks `archived=0`; archived files can be re-registered.
- Tag normalization: spaces become hyphens, max 20 tags, max 50 chars each.
- Search snippets are max 160 chars with ellipsis.

## Related tests

- `tests/knowledge/test_knowledge_repository.py`
- `tests/knowledge/test_knowledge_service.py`
- `tests/knowledge/test_knowledge_validation.py`
- `tests/knowledge/test_knowledge_search.py`
- `tests/test_knowledge_commands.py`
- `tests/test_knowledge_dashboard.py`
