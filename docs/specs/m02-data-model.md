# M2 — Data model + migrations

## What
Six Postgres tables created by Alembic migrations, a SQLAlchemy model per table,
and a Pydantic "read" model per entity.

| Table | Key columns |
|---|---|
| accounts | id, country (2 letters), currency (3 letters), status (active/suspended/closed), created_at |
| deposits | id, account_id → accounts, amount_minor, currency, method (card/upi/bank/wallet), created_at |
| bets | id, account_id → accounts, event_ref, market, selection, stake_minor, currency (3 letters), odds, status (open/won/lost/void), placed_at, settled_at?, payout_minor? |
| alerts | id, account_id → accounts, case_id → cases?, rule, severity (low/medium/high), details (JSONB), created_at |
| cases | id, status (open/investigating/closed), opened_at, closed_at?, resolution? |
| alert_labels | alert_id → alerts (PK), label (fraud/benign), scenario, created_at |

`?` = may be empty (nullable). No names, emails or phone numbers: accounts are synthetic and PII-free.

## Why
Every later milestone reads or writes these tables: the simulator fills them (M3),
agent tools query them (M4), the agent works on cases (M5).
Migrations make schema changes repeatable, reviewable and reversible on Mac, CI and cloud.

## Decisions
- Money = integer minor units (`*_minor BIGINT`, e.g. ₹250.75 → 25075) + currency. Never float.
- Odds = NUMERIC(8,3) ↔ Python Decimal (not money, but still exact).
- IDs = UUID, generated in Python. (new) UUIDv7 if our Python version has it (time-ordered → faster inserts into indexes), else v4. Claude Code checks, doesn't guess.
  **Checked: uuid4.** UUIDv7 not available on Python 3.12 (`uuid.uuid7` arrives in 3.14); revisit at M14 load testing.
- All timestamps = `timestamptz`, stored in UTC.
  No created_at default: simulator sets times explicitly; revisit in M5.
- Fraud labels live only in `alert_labels`. Agent tools will never get access to it (enforced with a DB role in M4). Today: separate table only.
- (new) Allowed values (status, severity, method…) = TEXT + CHECK constraint, not Postgres ENUM types. Easier to change later in a migration.
- (new) Database rules, not just Python rules: amounts > 0, odds > 1.000, foreign keys, NOT NULL. Bad data is rejected even if some future code forgets to validate.
- Multi-column CHECKs:
  - bets: status open → settled_at and payout_minor both empty; won/lost/void → settled_at set; payout_minor ≥ 0.
  - cases: status closed → closed_at set.
- Bets carry their own currency (CHAR(3)), like deposits; no "account currency" assumption.
- Constraint naming convention on the SQLAlchemy MetaData, so constraint names are stable
  (downgrades and later ALTERs don't depend on Postgres-generated names).
- Tests use a separate database, `sportsops_test`, via `TEST_DATABASE_URL` (the "downgrade base"
  test would otherwise wipe dev data). Unset locally → integration tests skip with a loud reason;
  unset in CI (`APP_ENV=ci`) → they fail.
  - CI: the Postgres service container creates it (`POSTGRES_DB: sportsops_test`).
  - Mac: once, `docker compose exec postgres createdb -U sportsops sportsops_test`.
    Not an init script: those only run on an empty volume, so the existing volume would still need the command.
- (new) Index every foreign key column, plus bets(account_id, placed_at) for "recent bets of an account".
- (new) Migrations: Alembic autogenerate drafts, a human reviews every line before commit.
- (new) CI gets a Postgres service container so the migration tests run on every PR, not only on my Mac.

## Done when
- [ ] `uv run alembic upgrade head` on an empty DB creates all 6 tables.
- [ ] Test: upgrade → downgrade base → upgrade succeeds (proves reversibility).
- [ ] Test: models and migrations are in sync (autogenerate finds no difference).
- [ ] Tests: DB rejects a negative deposit, odds ≤ 1, a deposit for a non-existent account, an unknown status.
- [ ] Tests: DB rejects an open bet with settled_at/payout, a settled bet without settled_at, a negative payout, a closed case without closed_at.
- [ ] Test: Pydantic read models build from DB rows; money stays an int; odds stay Decimal.
- [ ] Integration tests run in CI against real Postgres; ruff, mypy (strict), pytest green.
- [ ] Break it by hand: downgrade, then upgrade, on my Mac; insert bad rows with psql and watch them fail.
- [ ] Card `docs/cards/data-model.md` written by me.

## Not today
Seed data / simulator and label contents (M3) · DB roles for agent tools (M4) · API endpoints for these tables ·
"Create" Pydantic models (added when something creates data) · pgvector / document tables (M6) · partitioning (Phase 2).
