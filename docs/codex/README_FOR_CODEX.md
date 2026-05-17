# README for Codex

Use this directory to continue Atenas without relying on long chat context.

## Start here

1. Read:

```text
docs/phases/README.md
docs/codex/MASTER_CODEX_HANDOFF.md
```

2. Identify the current phase.

3. Read the relevant phase spec:

```text
docs/phases/phase-06-notes-files-foundation.md
docs/phases/phase-07-local-llm-selected-notes.md
docs/phases/phase-08-controlled-rag-foundation.md
```

4. Run tests:

```bash
python3 -m pytest
```

5. Implement only the active phase.

## Core rule

Do not skip foundation phases.

Correct order:

```text
structured data -> validated input -> notes/files -> local LLM -> RAG
```

Incorrect order:

```text
LLM/RAG first -> messy prompts -> unreliable product
```

## Reporting

Always report:

- changed files
- added files
- test results
- skipped/out-of-scope items
- next phase
