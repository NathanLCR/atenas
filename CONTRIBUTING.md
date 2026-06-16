# Contributing to Atenas

Thanks for your interest in Atenas. This guide covers the workflow and the
rules that keep the project coherent. The authoritative, always-current rules
live in [`CLAUDE.md`](CLAUDE.md); this document summarizes them for humans.

## Getting set up

Follow [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) for a fresh-clone
setup. For development you mainly need:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/pytest -q
```

The test suite mocks LLM providers and uses isolated databases, so it runs
without a live Ollama or a Telegram token.

## Project direction

Atenas is a **local-running, Telegram-first** LLM study assistant. The
dashboard and REST API are local support surfaces, not remote product
surfaces, unless a future spec adds authentication and deployment hardening.
Read these before making non-trivial changes:

1. `docs/AGENT_LOOP.md`
2. `docs/PRODUCT_SPEC.md`
3. `docs/ARCHITECTURE.md`
4. `docs/SECURITY.md`
5. `docs/AGENT_POLICY.md`
6. `docs/REQUIREMENTS.md`

## Working agreements

- Keep scope tight: do what was asked and prefer small, reviewable changes.
- Read relevant files before editing, and preserve unrelated local changes.
- Keep docs, tests, and code aligned in the same change.
- Keep files under 500 lines unless there is a documented reason.
- Validate input at system boundaries.
- Never commit secrets, `.env`, tokens, local databases, generated tool
  state, or dependency caches.

## Architecture rules

- Dependencies flow `app -> core`, never `core -> app`.
- `app/` wires Telegram, FastAPI, config, startup, and response formatting.
- `core/` owns services, policy, data models, repositories, retrieval, and
  LLM clients.
- Settings are injected into core services. Do not import `app.config` inside
  `core/`.
- The LLM sees tool schemas, not service/repository objects. Tool handlers call
  services; they do not duplicate business logic.

## Tool safety

Writes go through the action-tier model (see `docs/AGENT_LOOP.md`):

- **Read** tools may run after allowlist auth.
- **Auto-tier** writes (reversible, local, low-risk) validate arguments,
  resolve natural-language references to stable IDs, run the policy engine,
  execute through core services, and log the outcome.
- **Confirm-first** writes (destructive or egress) additionally create a
  pending action and require explicit Telegram confirmation before execution.
- The LLM never sets confirmation flags and never executes writes directly.

## Tests

- Add or update tests alongside code and docs.
- Tests must mock LLM providers and use isolated settings/databases; they must
  not fall back to the local `.env` or real local database.
- Run the full suite before opening a pull request: `.venv/bin/pytest -q`.
- Do not run npm build/test commands — Atenas is a Python project.

## Commits and pull requests

- Use clear, conventional-style commit messages
  (`fix:`, `feat:`, `docs:`, `ci:`, `chore:`).
- Keep each pull request focused on one concern.
- Describe what changed and why, and confirm the test suite passes.
- Update `CHANGELOG.md` under the `Unreleased` section for user-facing changes.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
