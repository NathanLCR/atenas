# Database Schema

## Engine

SQLite with WAL mode and foreign keys enabled.

## Schema initialization

`core/db.py` contains `SCHEMA_SQL` with all `CREATE TABLE IF NOT EXISTS` statements. `init_db()` runs the schema script and applies Phase 3 migrations for backward compatibility.

## Tables

### Academic tables (TEXT UUID IDs)

| Table | ID type | Key columns |
|-------|---------|-------------|
| `study_modules` | TEXT UUID | code, name, lecturer |
| `class_sessions` | TEXT UUID | module_id, title, weekday, start_time, end_time |
| `work_shifts` | TEXT UUID | title, start_at, end_at, date |
| `assignments` | TEXT UUID | module_id, title, due_at, status, priority |
| `study_blocks` | TEXT UUID | title, date, start_time, end_time, intensity |
| `tasks` | TEXT UUID | title, domain, module_id, status |

### Knowledge tables (INTEGER AUTOINCREMENT IDs)

| Table | ID type | Key columns |
|-------|---------|-------------|
| `notes` | INTEGER | title, body, module_id, assignment_id, source_type, tags, archived |
| `files` | INTEGER | path, filename, module_id, assignment_id, file_type, tags, archived |
| `note_file_links` | INTEGER | note_id, file_id (UNIQUE pair) |

### Infrastructure tables

| Table | Purpose |
|-------|---------|
| `documents` | Document metadata (legacy RAG) |
| `chunks` | Document text chunks (legacy RAG) |
| `nodes` | Knowledge graph nodes (legacy) |
| `edges` | Knowledge graph edges (legacy) |
| `memory_items` | Memory storage |
| `llm_calls` | LLM call audit log |

## Important constraints

- **Academic IDs are TEXT UUIDs**; knowledge IDs are **INTEGER AUTOINCREMENT**. Do not mix them.
- Foreign keys exist between knowledge tables and academic tables but are not enforced for legacy tables.
- `tags` stored as comma-separated text (not normalized tag tables).
- `archived` is INTEGER 0/1 for soft delete on notes and files.
- Datetimes stored as ISO 8601 strings.

## Indexes

Key indexes on: status, due_date, date, module code, task type, provider, archived flags.

## Migrations

`_apply_phase3_migrations()` adds columns to existing databases created before Phase 3. Uses `_ensure_column()` for idempotent ALTER TABLE.

## Pitfalls

- Adding columns to existing tables requires `_ensure_column()` for migration safety.
- `VALID_TABLE_NAMES` in `db.py` must be updated when adding new tables.
- Foreign key constraints on knowledge→academic tables may fail if referenced academic records don't exist.
