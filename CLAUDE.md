# Project: Agentic Sports Ops Platform

> Global rules live in ~/.claude/CLAUDE.md. This file adds only what is specific to this repo.

## Purpose
An internal AI operations platform for regulated risk and compliance work, using a simulated
sportsbook as the worked example. Analysts investigate streamed risk alerts (workflow A) and ask
multi-document policy questions (workflow B). Every answer is evidence-backed; every consequential
action needs human approval. Headline result: a measured comparison of rules vs single LLM call vs
single agent vs multi-agent (systems S0-S3). All data is public or synthetic; nothing from any
former employer.

## Sources of truth (read these, never rely on memory)
- `docs/progress.md` — where we are and the exact next step. **Read it at the start of every session.**
- `docs/plan.md` — the 28-day plan and later phases.
- `docs/architecture.md` — components, flows, scale targets.
- `docs/specs/` — one spec per day/module, written before code. **The spec wins over your ideas;**
  if the spec looks wrong, say so and stop; don't silently deviate.
- `docs/decisions/` — ADRs. `docs/cards/` — component cards.

## Architecture (short)
- `src/app/api/` FastAPI routers · `src/app/worker/` event consumer + case runner
- `src/app/agents/` LangGraph graphs, state · `src/app/prompts/` versioned prompt files
- `src/app/guardrails/` validation, permissions, budgets · `src/app/llm/` provider interface + router
- `src/app/schemas/` pydantic models · `mcp_servers/` one folder per MCP server
- `sim/` simulator + data loaders · `retrieval/` ingestion, parsing, search, rerank · `ml/` risk model
- `evals/` datasets, scorers, baselines S0-S3 · `tests/` unit, integration, chaos
(Folders are created when their day arrives, not before.)

## Commands
- Sync: `uv sync` · Tests: `uv run pytest` · Lint/format: `uv run ruff check . --fix && uv run ruff format .`
- Types: `uv run mypy` · Evals: `uv run python -m evals.run_evals`
- Stack: `docker compose up -d` · Logs: `docker compose logs -f <service>`

## Working rules for this repo
- One day/module per branch: `feat/dayNN-<slug>`. Work only on the current day's spec.
- Plan first (plan mode), wait for approval, then build in small slices; explain each file you change.
- Never claim something works without showing the command and its output.
- Code facts: read the file and cite `path:line`; don't answer from memory.
- Library facts: check the installed version (`uv tree`, `uv pip show <pkg>`) and current docs before
  using an API you're unsure of. Say "I'm not sure" rather than guess.
- Tests never call real LLM APIs (use the fake provider or recorded responses).
- No new dependency without saying why and what the alternatives were.
- At the end of a session, update `docs/progress.md` (done, open issues, exact next step).

## Lessons learned
<!-- One line each time you correct a mistake Claude made in this repo. -->
