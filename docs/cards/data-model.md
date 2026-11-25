# Card — Data model + migrations (M2)

## What it is
Six Postgres tables (accounts, deposits, bets, alerts, cases, alert_labels), described in Python
(SQLAlchemy models), created by a versioned Alembic migration, and read out through strict
Pydantic read models.
Story: draw it (models) → build it (migration) → guard it (constraints) → box it (read models).

## Why we need it
- Every later milestone uses these tables: the simulator fills them (M3), agent tools read them (M4),
  the agent works on cases (M5), evals compare verdicts with alert_labels (M9).
- Migrations make schema changes repeatable, reviewable and reversible on Mac, CI and cloud.

## What breaks without it
- No migrations → Mac, CI and cloud schemas drift; nobody can review or undo a change.
- No DB constraints → bad rows (negative stake, odds ≤ 1, bet for a non-existent customer) get saved
  whenever some code forgets to validate, and the agent reasons from impossible data.
- Labels on the alerts table → agent tools could read the answer key; evaluation becomes fake (leakage).

## Key decisions (and alternatives rejected)
| Decision | Rejected alternative | Why |
|---|---|---|
| Money = integer minor units (₹250.75 → 25075) + currency | float | floats can't store 0.10 exactly (0.1 + 0.2 ≠ 0.3); balances drift |
| Odds = NUMERIC(8,3) ↔ Decimal | float | exact decimals |
| IDs = UUID v4, created in Python | auto-increment; UUIDv7 | IDs made anywhere without asking the DB; v7 needs Python 3.14 → revisit at M14 |
| Timestamps = timestamptz, UTC | naive timestamps | "20:00" means nothing without a timezone |
| Allowed values = TEXT + CHECK | Postgres ENUM | easier to change in a migration |
| Fraud labels in a separate table | label column on alerts | agent tools will get no access (DB role in M4) |
| No ON DELETE cascade | cascade | audit/financial data must never vanish; accounts get closed, not deleted |
| Read models: strict + frozen | lenient Pydantic | lenient mode silently converts float → Decimal and hides the bug |

## Behaviour under failure
- Migration fails halfway → whole upgrade rolls back (Postgres transactional DDL); nothing half-built.
- Bad row arrives → rejected by a named constraint (e.g. ck_deposits_amount_positive); the name tells you which rule.
- Delete an account that has deposits → blocked by the foreign key.
- Tests can never wipe dev data: they only run on a database whose name ends in _test, and fail
  (not skip) in CI if TEST_DATABASE_URL is missing.
- Known limit: a CHECK sees only its own row, so bets.currency = account currency isn't enforced
  (needs a trigger); the simulator keeps them consistent.
- Migration blocked by a long query → gives up after 5 s (lock_timeout) and rolls back, instead of freezing every query behind it.

## How it scales
- Indexes on every foreign key; bets(account_id, placed_at) also serves lookups by account alone (left-prefix rule).
- Each extra index slows every insert → only the indexes we need.
- At Sportsbet volume: UUIDv7 for index-friendly inserts (M14); partition bets by time (Phase 2);
  big-table changes need care (CREATE INDEX CONCURRENTLY).

## How it maps to a large company
- Migrations run automatically in the deploy pipeline, never by hand in production.
- Zero-downtime changes use expand → migrate → contract; production usually rolls forward, not down.
- Sportsbook tables would be owned by the platform team; the AI engineer owns the agent-facing
  design: cases (agent's workspace) and the protected labels.
- Schema changes can break CDC/warehouse consumers → schema-evolution rules matter.

## What we monitor
- Migration state per environment (alembic current = head?).
- Constraint-violation errors in logs (a spike = a bug upstream, e.g. the simulator).
- Table sizes and slow queries as data grows.

## Proof (how I know it works)
- 90 tests: 32 integration tests against real Postgres (6 tables created; up → down → up; models and migrations in sync; 25 constraint tests that check which rule fired; read models keep int / Decimal).
- CI runs them against a Postgres service container (same image as compose).
- By hand on dev: upgrade → downgrade base → upgrade; inserted bad rows via psql → 3 guards fired.

## Interview questions
1. Why not float for money? → Floats are binary fractions; 0.10 isn't exact, so sums drift. Integer minor units are exact; Stripe does the same.
2. How do you change a schema without downtime? → Expand → migrate → contract, with migrations run in the pipeline.
3. How do you stop an agent from cheating on its evaluation? → Labels in a separate table its tools can't read; enforced by a DB role.
4. Why check constraints in the DB if Python validates? → The DB is the last line of defence; any code path, any tool, any bug is still stopped.
5. CHECK vs NOT NULL? → A CHECK passes on NULL; NOT NULL is a separate rule.
