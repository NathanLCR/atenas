# Codex Prompt Template — Atenas Phase X

You are working on the `atenas-core` repo.

## Current baseline

Run first:

```bash
python3 -m pytest
```

Do not start implementation unless the current baseline passes.

## Task

Implement:

```text
Phase X — <phase name>
```

Read the phase spec in:

```text
docs/phases/<phase-file>.md
```

## Hard constraints

Preserve all existing tests.

Do not add out-of-scope features.

Do not add unnecessary dependencies.

Do not hardcode personal data.

Do not weaken tests to make implementation pass.

## Implementation order

1. Inspect existing repo structure.
2. Identify relevant services/repositories/routes/templates/tests.
3. Implement minimal phase scope.
4. Add tests.
5. Run full suite.
6. Report summary.

## Final response format

```markdown
# Phase X implementation summary

## Changed
- ...

## Added
- ...

## Tests
- Command:
- Total:
- Passed:
- Failed:
- Warnings:

## Notes
- ...

## Next recommended phase
- ...
```
