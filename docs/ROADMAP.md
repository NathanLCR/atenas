# Atenas — Product Roadmap

Product-owner review as of 2026-11-19. This file ranks what stands between
Atenas and a product a stranger can adopt, and a portfolio piece a reviewer can
judge in five minutes. Contracts stay in `PRODUCT_SPEC.md` and
`REQUIREMENTS.md`; this file only orders the work.

## Where Atenas stands

The engineering core is strong: a bounded tool-calling agent, policy tiers
enforced in code, a deterministic fatigue-aware planner with falsifiable
acceptance tests, FTS5 retrieval, an audit trail, and roughly 700 offline tests.

The product around that core was weaker than the code. The review found:

| # | Finding | Impact | Status |
|---|---|---|---|
| 1 | `main` was red: local-only planning notes were untracked but 3 tests and 21 doc links still depended on them | CI badge on the README showed failing | Fixed |
| 2 | Docker quickstart returned 403 on every request (bridge-gateway peer rejected by the local-only guard) and could not reach host Ollama | Documented install path did not work | Fixed (`TRUSTED_CLIENT_NETWORKS`, fixed compose subnet, `host.docker.internal`) |
| 3 | `/start` and `/help` were not registered; no Telegram command menu | A new user's first message got "Unknown command" | Fixed |
| 4 | No typing indicator during 10–60 s local-model turns | Bot looks dead | Fixed |
| 5 | Files could only be added by typing a server filesystem path | Unusable from a phone | Fixed (Telegram document upload) |
| 6 | Registered PDFs were never indexed for retrieval | Core study use case (slides, papers) silently failed | Fixed (`pypdf` extraction, "not searchable" warnings) |
| 7 | Docs contradicted each other on whether the 2026-06-11 audit defects were open | Reviewer cannot trust the docs | Fixed |
| 8 | 18 dependency advisories (starlette via pinned FastAPI, pytest); test deps shipped as runtime deps | Supply-chain hygiene | Fixed (bumped, `requirements-dev.txt`, `pip-audit` in CI, Dependabot) |
| 9 | No lint in CI; 123 ruff findings | Code-quality signal | Fixed (ruff in CI) |
| 10 | Empty first run: no way to evaluate the planner without a Telegram bot | Reviewer bounces | Fixed (`atenas demo`) |
| 11 | Dashboard labelled work + class + free time as "committed study"; author's school hard-coded in the template | Misleading numbers, personal data in product UI | Fixed |

## Follow-ups from the fixes

- **Smoke-test on real infrastructure.** The Docker setup was validated with
  `docker compose config` only; build it and confirm the dashboard answers via
  the trusted gateway on Linux and Docker Desktop. Run a live Telegram session
  on `python-telegram-bot` 22 (the test suite mocks Telegram).
- **Route uploads through the policy engine.** Telegram uploads and
  `/add_file` are validated and audit-logged but skip `PolicyEngine`, which
  CLAUDE.md requires for auto-tier writes.
- **Remove the temporary ruff per-file ignores** on `app/bot.py`,
  `app/cli.py`, `app/dashboard.py`, `core/retrieval/*`, `core/knowledge/*`.
- **Timezone defaults.** Some `core/` services and `app/bot.py` still default to
  `Europe/Dublin`; settings default to `UTC`. Make settings the only source.
- **Bind-mount permissions.** `./data` owned by the host user may not be
  writable by the container's `appuser`; document or set `user:` in compose.

## Now — finish v1 polish (small, high leverage)

1. **Release v0.2.0 properly.** The CHANGELOG has `0.1.0` but the repo has no
   git tags or GitHub releases. Tag, publish release notes, and single-source the
   version (`pyproject.toml` vs `APP_VERSION` in settings).
2. **Show the primary interface.** The README shows the dashboard, a secondary
   surface. Add a 30–45 s Telegram screen recording (plain message → tool calls →
   confirm-first delete → audit trail) and a Mermaid architecture diagram.
3. **Inline confirmation buttons.** Replace typed `yes`/`no` with Telegram inline
   keyboards for pending actions. The confirmation still runs through the
   existing policy path; only the input method changes.
4. **Remove the legacy NL path.** `core/nl/router.py`, `core/nl/classifier.py`
   and `core/llm_router.py` (~1,400 lines) are not used by `app/`; they are only
   kept alive by their own tests. Delete them, or document why they stay.
5. **Pay down the 500-line rule.** `app/bot.py` (~1,800), `core/nl/tools.py`
   (~1,800), `core/academic/service.py` (~900), `core/academic/importers.py`
   (~700) and `core/academic/repository.py` (~620) break the project's own
   rule. Split them by domain (schedule, knowledge, LLM helpers) along the lines
   the command catalog already draws.

## Next — prove the agent claim (what sets this portfolio piece apart)

6. **Agent evaluation harness.** The core claim is that small local models work
   when given strong tools. Today that claim has no evidence: every test mocks
   the model. Add `evals/` with ~50 golden conversations (single-tool,
   multi-step, ambiguous-reference, confirm-first, prompt-injection-in-notes,
   out-of-scope) and a runner that scores tool-choice accuracy, argument
   validity, repair rate, policy violations, and p50/p95 latency per model
   profile (`llama3.2`, `llama3.1:8b`, `qwen2.5:7b`, …). Commit the results
   table to the README and re-run it whenever a prompt or toolset changes. A
   scripted-model mode keeps it runnable in CI.
7. **Plan adherence loop.** Atenas plans, but never learns whether the plan
   happened. Add a one-tap end-of-block check-in ("Did you do 45 min of DL
   Lab 03? ✅ / partial / ❌") that updates `completed_hours`, and a weekly
   review that reports planned vs. done and adjusts future estimates. This turns
   a planner into a coach and gives the product its retention metric.
8. **Calendar interop.** Accept university timetables as `.ics` (upload or
   URL) and export the study plan as an `.ics` feed. Entering classes by hand
   with `/add_class key=value` is the biggest onboarding cost.

## Later — deepen the study value

9. **Spaced repetition.** `/flashcards_note` creates cards and then forgets
   them. Store the cards and schedule reviews (SM-2 or FSRS), drive daily reviews
   with inline buttons, and slot review time into the planner as a block type.
10. **Voice notes.** Shift workers capture tasks on the move. Transcribe
    Telegram voice messages locally (whisper.cpp / faster-whisper) and feed the
    transcript to the agent as user input.
11. **Data ownership.** `atenas export` (JSON + Markdown) and a confirm-first
    `atenas forget` wipe, to go with the existing backup/restore.
12. **Rota capture.** Optional local vision model (e.g. `llava`) that turns a
    photo of a work rota into proposed shifts, confirmed before they are saved.

## Explicitly not planned

Multi-user SaaS, public dashboard exposure, and cloud-first LLM use stay out of
scope (see `PRODUCT_SPEC.md`). Each would need its own auth and threat-model
spec first.
