# Skill Spec — Memory

## Purpose
Store, retrieve, and search memory items. Memory is the foundation of Atenas's context awareness. Files must always be human-inspectable.

## Commands

| Command | Description |
|---|---|
| `/memory add <text>` | Extract and store a memory item |
| `/memory search <query>` | Search stored items by keyword |
| `/memory show <topic>` | Show items for a topic |

## LLM Usage
- `/memory add`: local LLM extracts structured fields. Schema: `MemoryItemExtracted`.
- `should_store=false` → model declines to store noise.
- `confidence < 0.65` → ask user to clarify before storing.
- Fallback: cloud LLM if local fails validation twice.

## Storage
- Write: `memory/notes/<domain>/<YYYY-MM-DD>-<slug>.md` + SQLite `memory_items`
- Read: SQLite `memory_items` for search

## Safety Rules
1. Never overwrite silently. Log previous value.
2. Sensitive content never sent to cloud without confirmation.
3. Low confidence triggers confirmation.
4. No delete in v1.

## Phase
Phase 4. Not implemented in Phase 1.
