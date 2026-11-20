# Progress

> Read at the start of every session (by you and by Claude Code). Update at the end of every session.

## Current
- **Day:** 1 — Kickoff (infra + health)
- **Branch:** feat/day01-kickoff (7 commits ahead of main incl. this update; not pushed)
- **Status:** built and reviewed; all local checks green; waiting for PR + CI

## Exact next step
Push feat/day01-kickoff, open the PR, confirm CI is green, merge. Then write the Day 2 spec
(docs/specs/day02-<slug>.md: Postgres schema + Alembic, Pydantic models per entity) and run /start-day.

## Done
- Setup (2026-11-19): template repo public + CI green; platform repo created from it; PR #1 rename, PR #2 kickoff kit; /start-day verified (stops with no spec)
- Day 1 (2026-11-20): Postgres 18.7 + pgvector 0.8.7 and Redis 8.10.3 in compose (healthchecks, 127.0.0.1-only ports, one .env for uv run and compose); `/health` = liveness only; new `/ready` checks both concurrently with a 1 s timeout (Postgres down → 503, Redis down → 200 degraded). 27 tests; break tests passed by hand (Redis stop, Postgres stop, Postgres pause → timeout in 1.01 s, app boot with Postgres down; all recover without app restart). Card: docs/cards/health-check.md. PR: not opened yet.

## Open questions / known issues
- **M1 (medium):** every /ready call opens a fresh Postgres + Redis connection with no cap; ~100 concurrent calls could exhaust Postgres `max_connections` (100). Safe today (127.0.0.1 only). Fix before /ready faces a load balancer: cache the result 1–2 s or allow one in-flight check (src/app/core/readiness.py, src/app/core/dependency_checks.py).
- **M2 (medium):** DATABASE_URL / REDIS_URL default to localhost, so a missing setting in staging/prod starts "fine" and only shows as /ready 503. Make them required when app_env is not local/ci (src/app/core/config.py).
- **L1 (low):** a WARNING is logged on every failed /ready poll (log noise during an outage). Consider logging state changes only (src/app/core/readiness.py).
- **L4 (low):** compose `env_file: required: false` is misleading (the `${POSTGRES_*:?}` checks need .env anyway), and the app container also receives POSTGRES_PASSWORD via env_file though it only needs DATABASE_URL (docker-compose.yml).
- Known constraint: POSTGRES_PASSWORD must be letters/numbers only (inserted into a URL unencoded). REDIS_URL must become SecretStr if Redis ever gets a password.

## Decisions since last update
- /health and /ready split (liveness vs readiness); Postgres critical, Redis optional until it stores idempotency keys / rate limits. See docs/specs/day01-kickoff.md.
- psycopg[binary] 3 over asyncpg (ships type hints, works with mypy strict); redis-py for Redis.
- Readiness probes do not retry (the caller's polling is the retry); redis-py's default 10 retries disabled on purpose.
- Postgres 18 over 19 (19 only ~2 months old; tooling may lag). PG18+ images need the volume at /var/lib/postgresql.
- No ADR written: these are recorded in the spec and commit messages. Consider an ADR if the Postgres version or Redis criticality is revisited.

## Things I don't fully understand yet (ask in the next mentoring chat)
-
