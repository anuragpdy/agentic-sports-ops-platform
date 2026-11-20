# Day 01 — Postgres + Redis, with /health and /ready

**Branch:** feat/day01-kickoff · **Plan row:** Day 1

## What
- Add Postgres (pgvector image, pinned version, named volume so data survives) and
  Redis (pinned version) to docker-compose.yml. Each gets a compose healthcheck.
  The app starts only after both are healthy.
- Keep GET /health exactly as it is: "am I alive?". It must NOT check Postgres or Redis.
- Add GET /ready: "can I serve right now?". It checks Postgres and Redis at the same time,
  each with a timeout, and reports each one's status and how long it took.
- New settings in Settings and .env.example (fake values):
  DATABASE_URL (secret), REDIS_URL, DEPENDENCY_CHECK_TIMEOUT_SECONDS (default 1.0).

## Why
- Every later day needs a permanent store (Postgres) and a fast cache (Redis).
- /health and /ready are separate so that a database outage makes the platform stop
  sending traffic, instead of restarting the app over and over (a restart storm).

## Decisions
- Postgres is critical: if it is down, /ready returns 503 with status "down".
- Redis is optional for now (only a cache): if it is down, /ready returns 200 with status "degraded".
  Revisit when Redis stores idempotency keys or rate limits.
- Each check has a timeout that covers the whole check, not only connecting.
- No connection is kept from startup: the app must start even if Postgres is down,
  and recover by itself when Postgres comes back.
- Responses never contain URLs, hostnames, passwords or error text. Only a reason:
  "timeout" or "connection_error".

## Contract (what /ready returns)
- 200 {"status":"ok","checks":{"postgres":{"status":"ok","latency_ms":4},"redis":{"status":"ok","latency_ms":1}}}
- 200 {"status":"degraded", ... "redis":{"status":"down","reason":"timeout"}}
- 503 {"status":"down", ... "postgres":{"status":"down","reason":"connection_error"}}

## Done when
- [ ] `docker compose up -d` → app, postgres, redis all "healthy" in `docker compose ps`
- [ ] `curl -i localhost:8000/health` → 200; `curl -i localhost:8000/ready` → 200 "ok"
- [ ] `docker compose stop redis` → /ready 200 "degraded"; /health still 200
- [ ] `docker compose stop postgres` → /ready 503 "down"; /health still 200
- [ ] `docker compose pause postgres` → /ready answers in under 2 s with reason "timeout"
- [ ] Start/unpause the services → /ready back to "ok" without restarting the app
- [ ] App starts while postgres is stopped (/health 200, /ready 503)
- [ ] Unit tests for /ready (all ok, redis down, postgres down, timeout) use fake checks:
      no real containers, no network. The existing 8 tests still pass
- [ ] ruff, format, mypy, pytest all green locally and in CI
- [ ] No password appears in any log line or response
- [ ] docs/cards/health-check.md written by me

## Not today
- Tables, migrations, ORM, connection pools
- Any data, any AI/LLM
- Integration tests with real containers in CI
- Kubernetes, metrics, tracing
- Rewriting the Problem section and ADR 0002 (moved to a later day)
