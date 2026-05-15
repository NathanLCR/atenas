# Atenas Core

Phase 1 foundation skeleton for Atenas, a local-first AI study operating system for working students.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

## Docker

```bash
docker-compose up
```

Phase 1 includes FastAPI health/status endpoints, SQLite initialization, structured logging, strict schemas, a policy engine, an action executor, a mock LLM router, and the deterministic status skill.

