# Card: Health and readiness checks (/health, /ready)

## What it is
Two endpoints. /health = "is the app itself alive?" (checks nothing else).
/ready = "can the app do useful work right now?" (checks Postgres and Redis).

## Why we need it
Machines decide automatically based on these answers: Docker, load balancers,
Kubernetes and uptime monitors. /health decides "restart the app or not".
/ready decides "send it traffic or not".
We keep them separate so we don't restart the app every time there is a
connection error to Postgres or Redis. Restarting the app can't fix the database.

## What breaks without it
- If /health checked the databases: a database outage makes every app copy
  restart again and again (restart storm), and they all hit the database at once
  when it comes back.
- With no /ready: traffic keeps going to an app that can't serve it.

## Alternatives and why not
- One endpoint that checks everything → restart storm (above).
- No timeout on checks → a frozen database makes /ready hang, and the app stalls too.
- Keep one connection open from startup → app crashes if the DB is down at boot,
  and keeps using a dead connection after the DB restarts.

## Behaviour under failure (tested by hand on 2026-11-20)
| What failed | /ready | /health |
|---|---|---|
| Redis stopped (non-critical) | 200 "degraded", reason connection_error | 200 |
| Postgres stopped (critical) | 503 "down", reason connection_error | 200 |
| Postgres frozen (paused) | 503 "down", reason timeout, answered in 1.01 s | 200 |
| App started while Postgres was down | 503, then "ok" by itself when Postgres returned | 200 |
Recovery: always back to "ok" without restarting the app.

## How it scales
Each /ready call opens a fresh Postgres and Redis connection. Postgres allows
about 100 connections, so a flood of /ready calls could use them all and block
real traffic (review finding M1). Fix before real traffic: cache the result for
1–2 s, or allow only one check at a time.

At Sportsbet scale (~2.4M customers) or Junglee scale (~150M users) there are many app copies, each polled every few seconds, so M1 becomes real: cache the /ready result and use a connection pool (or PgBouncer) instead of a fresh connection per check.

## How it maps to a large company
Kubernetes liveness probe = /health (failure → restart the container).
Kubernetes readiness probe = /ready (failure → stop sending traffic, no restart).

## What we monitor
- The "status" field: ok / degraded / down.
- latency_ms per dependency: slowly rising = trouble coming.
- WARNING log lines (dependency name, reason, error type; never passwords).

## Interview questions
1. Why are /health and /ready separate? What goes wrong in Kubernetes if the
   liveness probe checks Postgres during a 2-minute outage?
2. Why are retries off in the Redis probe? Why one asyncio.timeout around the
   whole check instead of the driver's connect timeout?
3. 50 pods, each polled every 2 s, each opening a fresh Postgres connection:
   what breaks first, and how would you fix it (cache, pool, PgBouncer)?
