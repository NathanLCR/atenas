# Core Knowledge — Notes, Files, Search, Retrieval (Phases 6 and 8)

## Purpose

Local-first knowledge layer for study notes, file metadata registry, note-file linking, deterministic keyword search, and controlled source-grounded retrieval over registered records.

## Files

| File | Role |
|------|------|
| `core/knowledge/models.py` | Pydantic models: Note, FileRecord, NoteFileLink, SearchResult |
| `core/knowledge/repository.py` | SQLite CRUD for notes, files, note_file_links |
| `core/knowledge/service.py` | Business logic, validation, module/assignment checks |
| `core/knowledge/validators.py` | Tag normalization, file type/mime derivation, field validation |
| `core/knowledge/search.py` | SQL LIKE search engine with deterministic ranking |
| `core/retrieval/chunking.py` | Deterministic note/file text chunking |
| `core/retrieval/vector_store.py` | SQLite-backed `retrieval_chunks` index and lexical scoring |
| `core/retrieval/service.py` | Rebuilds the retrieval index, retrieves sources, calls local Ollama answers |
| `core/retrieval/models.py` | Retrieval chunks, sources, answers, and index stats |
| `core/retrieval/prompts.py` | Source-grounded answer prompt construction |

## Main classes

- `KnowledgeService` — primary entry point for knowledge operations.
- `KnowledgeRepository` — SQLite persistence for knowledge tables.
- `SearchEngine` — keyword search over notes and file metadata.
- `RetrievalService` — controlled RAG entry point for `/ask_notes`, `/ask_note`, `/sources`, and dashboard retrieval.
- `RetrievalVectorStore` — deterministic SQLite chunk index using sparse lexical scoring.
- `Note`, `FileRecord`, `SearchResult` — Pydantic models.
- `RetrievalChunk`, `RetrievedSource`, `RetrievalAnswer` — source-grounded retrieval models.

## Data flow

```text
/add_note → parse_kv_args → KnowledgeService.create_note() → validate → Repository → CommandResult
/search → KnowledgeService.search() → SearchEngine.search() → SQL LIKE → ranked results
/ask_notes → RetrievalService.rebuild_index() → retrieval_chunks → source list → local Ollama answer
```

## Important constraints

- Note/file IDs are INTEGER AUTOINCREMENT (different from academic UUID4 TEXT IDs).
- Tags stored as comma-separated lowercase hyphenated strings.
- Soft archive (`archived=1`); excluded from normal listing and search.
- File registration rejects missing paths by default (`allow_missing=False`).
- Duplicate file detection by normalized path.
- Search uses SQL LIKE only — no embeddings, no vector DB.
- Retrieval uses deterministic chunking plus SQLite lexical scoring; no vector DB is required.
- Retrieval includes registered notes and supported text files only.
- Archived notes/files are excluded from indexing and retrieval.
- Unsupported or unreadable registered files are skipped during index rebuild.
- Generated answers must have retrieved sources; otherwise return the no-source fallback.
- No web search, cloud fallback, automatic filesystem ingestion, OCR, or PDF parsing.

## Ranking (search)

1. Exact title match → 100
2. Title contains query → 80
3. Tag contains query → 60
4. Body/description/path contains query → 40
5. Ordered by `updated_at DESC`

## Retrieval behavior

1. Rebuilds the `retrieval_chunks` table from non-archived records on each retrieval request.
2. Applies optional `note_id`, `module_id`, and `assignment_id` filters.
3. Scores chunks lexically against the question and returns source labels such as `N1.1` or `F3.2`.
4. Calls local Ollama only after at least one source is found.
5. If Ollama is unavailable, callers can still display the retrieved source cards.

## Pitfalls

- Do not mix knowledge INTEGER IDs with academic TEXT UUID IDs.
- `find_duplicate_file` checks `archived=0`; archived files can be re-registered.
- Tag normalization: spaces become hyphens, max 20 tags, max 50 chars each.
- Search snippets are max 160 chars with ellipsis.
- Retrieval note IDs are knowledge INTEGER IDs; module and assignment filters are academic TEXT IDs.
- `RetrievalService.rebuild_index()` deletes and recreates `retrieval_chunks`; do not treat the table as an append-only audit log.

## Related tests

- `tests/test_db.py`
- `tests/retrieval/test_chunking.py`
- `tests/retrieval/test_retrieval_service.py`
- `tests/test_retrieval_commands.py`
- `tests/test_retrieval_dashboard.py`
