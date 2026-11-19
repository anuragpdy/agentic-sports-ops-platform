# Project: <PROJECT NAME>

> Template defaults below. On a new project, fill in Purpose and Architecture first.
> Global rules live in ~/.claude/CLAUDE.md; this file only adds what is specific to this repo.

## Purpose
<One paragraph: what this system does, for whom, and why.>

## Architecture
- `src/app/api/` — FastAPI routers (HTTP only; no business logic)
- `src/app/core/` — config (`config.py`, env vars via pydantic-settings), logging
- `src/app/llm/` — `LLMProvider` interface + providers. Never call an LLM SDK from anywhere else.
- `src/app/prompts/` — prompt templates as versioned files
- `src/app/agents/`, `src/app/tools/` — workflows and agent-callable functions
- `src/app/schemas/` — pydantic models shared across layers
- `tests/` — pytest; `evals/` — datasets + runner for AI answer quality
- Details and diagrams: `docs/architecture.md`. Decisions: `docs/decisions/`.

## Commands
- Install / sync: `uv sync`
- Tests: `uv run pytest`
- Lint + format: `uv run ruff check . --fix && uv run ruff format .`
- Types: `uv run mypy`
- Evals: `uv run python -m evals.run_evals`
- Run API: `uv run uvicorn app.main:app --reload`
- Container: `docker compose up --build`

## Conventions
- All config comes from `app.core.config.get_settings()`. Never read `os.environ` directly.
- New env var → add to `Settings`, to `.env.example` (fake value) and to the README if user-facing.
- New LLM provider → implement `LLMProvider` in `src/app/llm/` and register it in `factory.py`.
- Tests must not call real LLM APIs; use the `fake` provider.
- "Done" = ruff, mypy, pytest and evals all pass (same as CI).

## Lessons learned
<!-- Add one line each time you correct a mistake Claude made in this repo. -->
