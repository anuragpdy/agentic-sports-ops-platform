# Progress

> Read at the start of every session (by you and by Claude Code). Update at the end of every session.

## Current
- **Milestone:** M3 (simulated sportsbook + ground truth) ▶ in progress. M2 merged as PR #5 (`6fa33b4`).
- **Branch:** feat/m03-simulator
- **Status:** S1–S4 done (create models, seeded core, stories + registry, alert rules); next S5.

## Exact next step
S5: labels from the registry (fraud only if the alert falls inside the episode window) +
leakage tests (D7). Then S6 (writer + `python -m app.sim` CLI, one transaction, refuse if
any table has rows), S7 (docs/cards/simulator.md, incl. the signal table), then open the PR.

## Done
- Setup (2026-11-19): template repo public + CI green; platform repo created from it; PR #1 rename, PR #2 kickoff kit; /start-day verified (stops with no spec)
- Day 1 (2026-11-20): Postgres 18.7 + pgvector 0.8.7 and Redis 8.10.3 in compose (healthchecks, 127.0.0.1-only ports, one .env for uv run and compose); `/health` = liveness only; new `/ready` checks both concurrently with a 1 s timeout (Postgres down → 503, Redis down → 200 degraded). 27 tests; break tests passed by hand (Redis stop, Postgres stop, Postgres pause → timeout in 1.01 s, app boot with Postgres down; all recover without app restart). Card: docs/cards/health-check.md. PR: PR #3.
- M2 (2026-11-25): six tables (accounts, deposits, bets, alerts, cases, alert_labels) via SQLAlchemy models + one reviewed Alembic migration; DB rules: FKs (no cascade), NOT NULL, CHECKs for amounts, odds > 1, ISO codes, allowed values, bet/case state, alerts.details is a JSON object; strict frozen Pydantic read models; migrations get connect_timeout 10 s + lock_timeout 5 s. 90 tests (32 integration against sportsops_test: up/down/up, no drift, 25 constraint tests naming the rule that fired, read models, lock timeout); CI runs them against a Postgres service container; pytest-timeout 60 s. Hand break tests done on dev. Card: docs/cards/data-model.md. PR #5, merged as 6fa33b4.
- M3 day 1 (2026-11-26): spec settled (95cfe5e); S1 strict create models, closes I5 + I6 (d58907d); S2 seeded core, single-currency AUD book (cc211b8); S3 fraud stories F1/F2 + look-alikes L1/L2 + in-memory registry (6ac1be9); S4 behaviour-only alert rules with cooldown + stake escalation (d4bea24); ordinary variety (match-day top-ups, high rollers) + scripts/sim_report.py (a7d5df6). Alert mix at 5,000 accounts, seed 42: fraud-in-episode 22.3%, look-alikes 26.0%, ordinary 51.5%. 194 tests.

## Open questions / known issues
- **I1 (medium):** every /ready call opens a fresh Postgres + Redis connection with no cap; ~100 concurrent calls could exhaust Postgres `max_connections` (100). Safe today (127.0.0.1 only). Fix before /ready faces a load balancer: cache the result 1–2 s or allow one in-flight check (src/app/core/readiness.py, src/app/core/dependency_checks.py).
- **I2 (medium):** DATABASE_URL / REDIS_URL default to localhost, so a missing setting in staging/prod starts "fine" and only shows as /ready 503. Make them required when app_env is not local/ci (src/app/core/config.py).
- **I3 (low):** a WARNING is logged on every failed /ready poll (log noise during an outage). Consider logging state changes only (src/app/core/readiness.py).
- **I4 (low):** compose `env_file: required: false` is misleading (the `${POSTGRES_*:?}` checks need .env anyway), and the app container also receives POSTGRES_PASSWORD via env_file though it only needs DATABASE_URL (docker-compose.yml).
- ~~**I5 (low):** odds NUMERIC(8,3) silently rounds extra decimals.~~ **Closed by d58907d:** `BetCreate` rejects odds that rounding to 3 dp would change, or that don't fit NUMERIC(8,3) (src/app/schemas/create.py).
- ~~**I6 (low):** a naive datetime is stored as if it were UTC.~~ **Closed by d58907d:** create models reject naive and non-UTC datetimes (src/app/schemas/create.py).
- **I7 (low, accepted scope):** rules across tables or columns not enforced: deposit/bet currency = account currency (needs a trigger), a lost bet with payout > 0, closed_at < opened_at, closed_at set on an open case (src/app/db/models.py bets/cases CHECKs). The simulator (M3) must keep them consistent; revisit if real writers appear (M5 case actions). The one-row part (lost bet → payout 0) is now enforced by `BetCreate` (d58907d).
- **I8 (low):** closed/suspended accounts keep betting to the end of the window (status is random and label-independent, D7, but has no effect on activity). Recorded in the M3 spec's "Known simplifications" (src/app/sim/population.py).
- **I9 (medium, revisit M9):** planted stories are perfectly separable by their full signal combination (every fraud account has it; no look-alike or ordinary account does: 0/4500 at seed 42). Before the benchmark, consider fraud variants missing one signal and harder look-alikes (src/app/sim/stories.py).
- Known constraint: POSTGRES_PASSWORD must be letters/numbers only (inserted into a URL unencoded). REDIS_URL must become SecretStr if Redis ever gets a password.

## Decisions since last update
- M3: single-currency AUD book (country AU), money assumptions in SimConfig; create models reject bad odds/times, never round.
  Alert de-duplication = 7-day cooldown per (account, rule), but stake rules escalate (a larger stake re-fires).
  Stake jump (J, relative to own history) is a separate signal from big stake (B, absolute); look-alikes borrow at most
  one fraud signal by exact quota. Details: docs/specs/m03-simulator.md, plus the S3/S4 commit messages (6ac1be9, d4bea24).
- /health and /ready split (liveness vs readiness); Postgres critical, Redis optional until it stores idempotency keys / rate limits. See docs/specs/day01-kickoff.md.
- psycopg[binary] 3 over asyncpg (ships type hints, works with mypy strict); redis-py for Redis.
- Readiness probes do not retry (the caller's polling is the retry); redis-py's default 10 retries disabled on purpose.
- Postgres 18 over 19 (19 only ~2 months old; tooling may lag). PG18+ images need the volume at /var/lib/postgresql.
- M2: decisions recorded in docs/specs/m02-data-model.md (uuid4 until M14; bets carry currency; TEXT + CHECK not ENUM; no created_at default until M5; no separate bets.account_id index; separate sportsops_test DB with *_test guard). Also: SQLAlchemy 2.1 + Alembic 1.20 (approved deps); pytest-timeout (dev); read models strict + frozen; value rules live only in the DB; first migration edited in place before push (same revision id) to add the details CHECK.
- Learned: `alembic check` does not compare CHECK constraints, so constraint tests (not the drift test) prove CHECKs exist.
- No ADR written: these are recorded in the spec and commit messages. Consider an ADR if the Postgres version or Redis criticality is revisited.

## Things I don't fully understand yet (ask in the next mentoring chat)
-
