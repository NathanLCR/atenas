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
- `sensitive=true` → item is stored but flagged; external LLM providers refuse
  to include it without explicit per-use confirmation.
- `confidence < MIN_CONFIDENCE_THRESHOLD` → ask user to clarify before
  storing (secondary signal only; see AGENT_POLICY "LLM Routing").
- External LLM fallback is disabled by default. If explicitly enabled, terminal
  failure still saves nothing, tells the user, and logs it.

## Storage
- Write: `memory/notes/<domain>/<YYYY-MM-DD>-<slug>.md` + SQLite `memory_items`
- Read: SQLite `memory_items` for search

## Safety Rules
1. Never overwrite silently. `overwrite_memory` is in `CONFIRMATION_REQUIRED`;
   log the previous value before applying.
2. `sensitive=true` content never sent to an external provider without explicit per-use
   confirmation (enforced via the `sensitive` field, not vibes).
3. Low (self-reported) confidence triggers a clarify prompt — it is a weak
   secondary signal, never a sole safety basis.
4. No delete in v1. `write_memory` is allowlisted; deletion is not.

## Phase
Phase 4. Not implemented in Phase 1.
