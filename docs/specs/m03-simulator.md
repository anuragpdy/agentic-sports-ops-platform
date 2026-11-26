# M3 — Simulated sportsbook + ground truth

## What
A seeded simulator (`src/app/sim/`) that fills five of the six M2 tables with realistic
synthetic data: ordinary customers, planted fraud stories, innocent look-alikes, rule-based
alerts, and an answer key (`alert_labels`) saying which alerts are really fraud.
`cases` stays empty and `alerts.case_id` is NULL: cases are analyst output (M5), and
pre-closed cases with a resolution could leak labels.
Strict create models guard everything written to the database.

## Why
The agent (M4+) needs data to investigate, and the evaluation (M9, M12) needs
labels we can trust. There is no public sportsbook data, so we generate it,
and we must be able to regenerate exactly the same exam.

## Decisions
- D1 Size: 5,000 accounts by default; `--accounts N` to change. Scale is M14.
  Prevalence lives in one config object: ~2% of accounts per fraud story, ~3% per
  look-alike, and `min_per_story` (default 50) accounts per story at minimum, so M9 has
  enough fraud alerts to sample from. The CLI refuses an N too small to meet the minimum
  while keeping most accounts ordinary. Tests build small runs (e.g. 200 accounts with a
  lower `min_per_story`) so they stay fast.
- D2 Scenarios: 2 fraud stories, each with a look-alike. Existing columns only;
  a story that needs a new column is dropped, not the schema changed.
  Events come from a synthetic fixture calendar (no external data).
  - F1 Deposit burst: new customer, many deposits in minutes, then one big bet at long odds.
    L1: established customer, several deposits on a busy match day, normal stakes.
  - F2 Sudden wake-up: quiet account returns with stakes far above its history.
    L2: customer returns after a break with stakes back at their own old peak.
  Alerts come from simple behaviour rules that fire on BOTH fraud and look-alikes
  (plus some on ordinary customers), so alerts are noisy, as in real life.
- D3 Determinism: one `random.Random(seed)` passed to every function; a fixed
  start date in code (never `now()`); UUIDs drawn from the seeded generator
  (never `uuid4()`).
- D4 (closes I5): `BetCreate` rejects odds that rounding to 3 dp would change
  (`2.1500` accepted, `2.1505` rejected) and odds that don't fit NUMERIC(8,3).
  Reject, never round.
- D5 (closes I6): create models reject naive datetimes and times not in UTC.
  No `CaseCreate` in M3 (M5 builds it).
- D6 Writing: build everything in memory → validate through create models → insert
  in ONE transaction. Refuse to run if ANY of the six M2 tables (including `cases`)
  already has rows.
  The simulator also keeps the I7 rules (currency matches the account; lost bet → payout 0).
- D7 Leakage: the alert rules never receive the label; labels are written in a separate
  step. `details` has the same keys for fraud and look-alikes and contains no label words.
  An alert is labelled `fraud` only if its account is in a fraud story AND the alert's
  time window overlaps the planted episode; otherwise `benign`.
  Rows are shuffled before insert; planted accounts are not clustered by `created_at` or
  ID; account `status` does not depend on the label.
  Every individual fraud signal (new account, deposit burst, big stake, long odds,
  wake-up after a break) also appears in some look-alikes; only the combination
  indicates fraud (e.g. some L1 customers are new, some L2 customers raise stakes).
- D8 Seeds: dev seed 42 (tuning); held-out seed 7 (final scores only, M9).

## Done when
- `uv run python -m app.sim --seed 42` fills an empty dev DB; a second run refuses with a clear message.
- Test: same seed twice → identical rows; different seed → different rows.
- Test: every alert has exactly one label; both labels occur; each fraud story has look-alikes.
- Test: leakage checks from D7 (same `details` keys, no label words, no clustering by
  `created_at`/ID, status independent of label).
- Test: for each story, no single signal alone separates fraud from its look-alikes.
- Test: create models reject odds `2.1505`, odds too large for NUMERIC(8,3), a naive
  datetime and a non-UTC time, each with a clear error; `2.1500` is accepted.
- By hand: a default 5,000-account run finishes; report how long it took.
- Test: generated data obeys the I7 rules.
- By hand: run it twice (see the refusal); check counts and one fraud story in psql.
- CI green with tests reported as passed, not skipped. Card: `docs/cards/simulator.md`.
- `progress.md`: I5 and I6 closed.

## Not today
Agent and MCP tools (M4) · DB role hiding `alert_labels` (M4) · scoring the agent (M9) ·
streaming alerts (M10) · scale (M14) · DB triggers for I7 · new columns ·
StatsBomb loader (plan Day 3; moved out of M3, synthetic fixtures instead) ·
`CaseCreate` and seeded cases (M5).
