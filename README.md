# ai-project-template

A production-ready starting point for AI engineering projects (LLM apps, agents, RAG).
Click **"Use this template"** on GitHub to start a new project with everything below already wired up.

## What's inside

| Area | Tooling |
|---|---|
| Python & dependencies | Python 3.12, [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`) |
| API | FastAPI with a `/health` endpoint |
| Config | `pydantic-settings` — all config from environment variables / `.env` |
| LLM access | One `LLMProvider` interface; a `fake` provider so everything runs with no API key |
| Quality | pytest (tests), ruff (lint + format), mypy (types), evals (AI answer quality) |
| Packaging | Dockerfile (multi-stage, non-root) + docker-compose |
| CI | GitHub Actions: lint, types, tests, evals, Docker build on every push/PR |
| AI pair-programming | `CLAUDE.md` + `.claude/settings.json` for Claude Code |

## Quick start

```bash
uv sync                                   # create .venv and install exact versions from uv.lock
cp .env.example .env                      # local config (never committed)
uv run pytest                             # tests
uv run ruff check . && uv run ruff format --check . && uv run mypy   # lint, format, types
uv run python -m evals.run_evals          # AI quality checks
uv run uvicorn app.main:app --reload      # API on http://127.0.0.1:8000/health
docker compose up --build                 # same app, inside a container
```

## Layout

```
src/app/
├── api/       HTTP endpoints (FastAPI routers)
├── core/      config, logging, shared plumbing
├── llm/       LLM providers behind one interface
├── prompts/   versioned prompt files
├── agents/    workflows / agent steps
├── tools/     functions an agent can call
└── schemas/   data shapes (pydantic models)
tests/         does the code work?
evals/         does the AI answer well?
docs/          architecture, playbook, decisions (ADRs)
```

## Starting a new project from this template

1. GitHub → **Use this template** → *Create a new repository*.
2. `git clone` it, then `uv sync`.
3. Rename the project in `pyproject.toml` (`name = ...`) and fill in `CLAUDE.md` and `docs/architecture.md`.
