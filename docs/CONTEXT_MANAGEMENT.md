# Atenas — Context & Memory Management Design

This document details how context, state, and memory are managed in the Atenas study assistant across various timescales and persistence tiers.

---

## Architecture Overview

Atenas structures user context into four distinct layers:

| Layer | Lifespan | Scope | Storage Mechanism | Implementation |
| :--- | :--- | :--- | :--- | :--- |
| **Short-Term Chat** | Session (12 messages) | Recent conversation flow | SQLite state persistence (injected into PTB `user_data`) | `core.nl.agent` |
| **Inter-Turn State** | Until confirmed/cancelled | Pending confirmations | SQLite state persistence (injected into PTB `user_data`) | `app.bot` |
| **Retrieval RAG** | Permanent | Academic source grounding | SQLite `retrieval_chunks` | `core.retrieval` |
| **Persistent Memory** | Permanent | User facts, preferences | SQLite `memory_items` | `core.memory_manager` |

---

## 1. Short-Term Chat Context (Conversation History)

The natural-language tool-agent loop relies on seeing recent user-assistant interactions to resolve pronouns, references, and maintain flow.

### Rules and Bounds
* **Turn Limits:** Fixed at `MAX_HISTORY_ITEMS = 12`. Only the last 12 messages are passed to the LLM context prompt to prevent token overflow.
* **Message Truncation:** To prevent arbitrary prompt injections, individual history messages are clamped to a maximum length of 2000 characters before assembly.
* **Format:** History is serialized to JSON and formatted into the `AGENT_PROMPT` system template.

---

## 2. Inter-Turn State (Confirmation Pipeline)

Any action classified in the `CONFIRM_FIRST` tier creates a pending state record that suspends general conversation until confirmed.

### Lifecycle Flow
1. **Proposal:** An ACT tool is invoked. If it is `CONFIRM_FIRST` (e.g. deletion, bulk modifications), it generates a `PendingToolAction` instead of writing immediately.
2. **Persistence:** The pending action is written to SQLite state, locking the user session.
3. **Response Interception:** The next user message is intercepted by the adapter. 
   * If the user says `yes`/`confirm`, the transaction executes.
   * If the user says `no`/`cancel`, the state is cleared and aborted.
   * Any other text prompts the user to choose `yes` or `no`.

---

## 3. Retrieval RAG Context (Academic Knowledge)

Document search indexes local note files and uploaded documents for factual study assistance.

### Design Principles
* **Separation of Concerns:** Search content is handled as **read-only data** inside prompts. Retrieved text chunks must never contain instructions that can manipulate the agent's tool execution.
* **Attribution:** Answers must explicitly cite sources (e.g., `[Note #12]`) or fall back to an explicit "no source found" statement when no relevant records exist.

---

## 4. Persistent Memory (User Profile)

Inferred facts, preferences, and long-term settings are kept in the `memory_items` table.

### Schema Structure
```sql
CREATE TABLE IF NOT EXISTS memory_items (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    summary     TEXT NOT NULL,
    domain      TEXT NOT NULL,
    topic       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    importance  TEXT NOT NULL DEFAULT 'medium',
    source      TEXT NOT NULL DEFAULT 'telegram',
    inferred    INTEGER NOT NULL DEFAULT 1,
    sensitive   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

### Operational Rules
* **Tool Access:** The LLM accesses memory through `read_memory` and `write_memory` tools.
* **Inference Labeling:** Any facts stored by the model automatically (inferred memory) must set `inferred = 1`. Directly stated facts set `inferred = 0`.
* **Conflict Resolution:** Memory entries cannot be silently overwritten. Updating requires updating the `updated_at` timestamp and generating a new summary or prompting the user.
