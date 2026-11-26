# M3 — Simulated sportsbook + ground truth

## What
A seeded simulator that fills the six M2 tables with realistic synthetic data:
ordinary customers, planted fraud stories, innocent look-alikes, rule-based alerts,
and an answer key (`alert_labels`) saying which alerts are really fraud.
Strict create models guard everything written to the database.

## Why
The agent (M4+) needs data to investigate, and the evaluation (M9, M12) needs
labels we can trust. There is no public sportsbook data, so we generate it,
and we must be able to regenerate exactly the same exam.

## Decisions
- D1 Size: ~1,000 accounts by default; `--accounts N` to change. Scale is M14.
- D2 Scenarios: 2 fraud stories, each with a look-alike. Existing columns only;
  a story that needs a new column is dropped, not the schema changed.
  - F1 Deposit burst: new customer, many deposits in minutes, then one big bet at long odds.
    L1: established customer, several deposits on a busy match day, normal stakes.
  - F2 Sudden wake-up: quiet account returns with stakes far above its history.
    L2: customer returns after a break with stakes back at their own old peak.
  Alerts come from simple behaviour rules that fire on BOTH fraud and look-alikes
  (plus some on ordinary customers), so alerts are noisy, as in real life.
- D3 Determinism: one `random.Random(seed)` passed to every function; a fixed
  start date in code (never `now()`); UUIDs drawn from the seeded generator
  (never `uuid4()`).
- D4 (closes I5): `BetCreate` rejects odds with more than 3 decimal places. Reject, never round.
- D5 (closes I6): create models reject naive datetimes and times not in UTC.
- D6 Writing: build everything in memory → validate through create models → insert
  in ONE transaction. Refuse to run if the simulated tables already have rows.
  The simulator also keeps the I7 rules (currency matches the account; lost bet → payout 0;
  closed_at after opened_at).
- D7 Leakage: the alert rules never receive the label; labels are written in a separate
  step. `details` has the same keys for fraud and look-alikes and contains no label words.
- D8 Seeds: dev seed 42 (tuning); held-out seed 7 (final scores only, M9).

## Done when
- `uv run python -m app.sim --seed 42` fills an empty dev DB; a second run refuses with a clear message.
- Test: same seed twice → identical rows; different seed → different rows.
- Test: every alert has exactly one label; both labels occur; each fraud story has look-alikes.
- Test: leakage checks from D7.
- Test: create models reject odds `2.1505`, a naive datetime and a non-UTC time, each with a clear error.
- Test: generated data obeys the I7 rules.
- By hand: run it twice (see the refusal); check counts and one fraud story in psql.
- CI green with tests reported as passed, not skipped. Card: `docs/cards/simulator.md`.
- `progress.md`: I5 and I6 closed.

## Not today
Agent and MCP tools (M4) · DB role hiding `alert_labels` (M4) · scoring the agent (M9) ·
streaming alerts (M10) · scale (M14) · DB triggers for I7 · new columns.
