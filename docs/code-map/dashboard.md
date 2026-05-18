# Dashboard

## Purpose

Read-only FastAPI web dashboard with Jinja2 templates for visualizing scheduling, knowledge, local LLM, and controlled retrieval data.

## Files

| File | Role |
|------|------|
| `app/dashboard.py` | FastAPI router with all dashboard routes |
| `app/main.py` | Application factory, static file mounting |
| `app/templates/base.html` | Base layout with sidebar navigation |
| `app/templates/home.html` | Overview page with quick links |
| `app/templates/week.html` | Weekly schedule and availability |
| `app/templates/deadlines.html` | Open assignments table |
| `app/templates/plan.html` | Study plan with blocks and warnings |
| `app/templates/data.html` | Data overview and command reference |
| `app/templates/logs.html` | LLM call log table |
| `app/templates/notes.html` | Notes card grid |
| `app/templates/files.html` | Files card grid |
| `app/templates/search.html` | Search form and results |
| `app/templates/retrieval.html` | Controlled retrieval question form, filters, answer, and source cards |
| `app/templates/llm.html` | Local LLM call history |
| `app/static/styles.css` | Single CSS file with design tokens |

## Routes

| Route | Template | Data source |
|-------|----------|-------------|
| `/dashboard/` | `home.html` | Settings |
| `/dashboard/week` | `week.html` | AcademicService.get_week_overview() |
| `/dashboard/deadlines` | `deadlines.html` | AcademicService.list_upcoming_assignments() |
| `/dashboard/plan` | `plan.html` | AcademicService.get_study_plan() |
| `/dashboard/data` | `data.html` | AcademicService.list_*() |
| `/dashboard/logs` | `logs.html` | Direct SQL on llm_calls |
| `/dashboard/notes` | `notes.html` | KnowledgeService.list_notes() |
| `/dashboard/files` | `files.html` | KnowledgeService.list_files() |
| `/dashboard/search` | `search.html` | KnowledgeService.search() |
| `/dashboard/retrieval` | `retrieval.html` | RetrievalService.answer_question() |
| `/dashboard/llm` | `llm.html` | Direct SQL on llm_calls |

## Key functions

- `_get_academic_service()` — builds AcademicService from request settings.
- `_get_knowledge_service()` — builds KnowledgeService from request settings.
- `_get_retrieval_service()` — builds RetrievalService with local Ollama settings.
- `_load_llm_call_records()` — direct SQL query for logs page.

## Important constraints

- Dashboard is **read-only** — no write forms.
- Static files served from `app/static/` via FastAPI `StaticFiles`.
- Templates extend `base.html` which provides sidebar navigation.
- CSS uses design tokens in `:root` for consistent theming.
- `/dashboard/retrieval` is read-only and uses GET query parameters only.
- Retrieval filters are `module` and `assignment`; they are passed to the retrieval layer as scope filters.
- If local Ollama is unavailable after sources are found, the dashboard should still show the source cards.

## Pitfalls

- Do not add dashboard write forms without API authentication.
- Template text changes may break existing tests that assert on response text.
- `_get_request_settings` falls back to global `get_settings()` if not in app state.
- Retrieval must not trigger automatic filesystem ingestion, web search, or cloud fallback.

## Related tests

- `tests/test_dashboard.py` — home and logs routes
- `tests/test_schedule_dashboard.py` — week, deadlines, plan routes
- `tests/test_retrieval_dashboard.py` — retrieval route, filters, fallback, and sources
