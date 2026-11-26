"""S2: simulator core + ordinary customers. Pure in-memory tests (no database)."""

import random
from collections import Counter
from datetime import timedelta
from decimal import Decimal

import pytest

from app.sim.build import generate
from app.sim.config import START, SimConfig
from app.sim.fixtures import build_calendar
from app.sim.ids import new_id
from app.sim.population import Population, draw_odds

SMALL = SimConfig(accounts=200)


@pytest.fixture(scope="module")
def pop() -> Population:
    return generate(42, SMALL)


def _dump(pop: Population) -> list[list[dict[str, object]]]:
    return [[row.model_dump() for row in rows] for rows in (pop.accounts, pop.deposits, pop.bets)]


# --- D3 determinism ------------------------------------------------------------------------


def test_same_seed_gives_identical_rows(pop: Population) -> None:
    assert _dump(generate(42, SMALL)) == _dump(pop)


def test_different_seed_gives_different_rows(pop: Population) -> None:
    other = generate(7, SMALL)

    assert {a.id for a in other.accounts}.isdisjoint({a.id for a in pop.accounts})
    assert _dump(other) != _dump(pop)


def test_seeded_ids_are_valid_v4_uuids() -> None:
    rng = random.Random(1)

    ids = [new_id(rng) for _ in range(1000)]

    assert all(i.version == 4 for i in ids)
    assert len(set(ids)) == len(ids)


# --- shape and sizes -----------------------------------------------------------------------


def test_one_account_per_requested_customer(pop: Population) -> None:
    assert len(pop.accounts) == SMALL.accounts
    assert len({a.id for a in pop.accounts}) == SMALL.accounts


def test_every_account_deposits_and_counts_stay_in_configured_range(pop: Population) -> None:
    deposits = Counter(d.account_id for d in pop.deposits)
    low, high = SMALL.deposits_per_account

    assert set(deposits) == {a.id for a in pop.accounts}
    assert all(low <= n <= high for n in deposits.values())


def test_all_times_are_inside_the_window_and_after_signup(pop: Population) -> None:
    created = {a.id: a.created_at for a in pop.accounts}

    for d in pop.deposits:
        assert max(created[d.account_id], START) <= d.created_at < SMALL.end
    for b in pop.bets:
        assert max(created[b.account_id], START) <= b.placed_at < SMALL.end
        assert b.settled_at is None or b.settled_at <= SMALL.end


def test_bets_come_after_first_deposit_and_before_kickoff(pop: Population) -> None:
    first_deposit: dict[object, object] = {}
    for d in sorted(pop.deposits, key=lambda d: d.created_at):
        first_deposit.setdefault(d.account_id, d.created_at)
    kickoff = {f.event_ref: f.kickoff for f in build_calendar(random.Random(42), SMALL)}

    for b in pop.bets:
        assert b.placed_at >= first_deposit[b.account_id]  # type: ignore[operator]
        assert b.placed_at < kickoff[b.event_ref]


def test_weekends_have_more_matches_than_weekdays() -> None:
    per_day = Counter(f.kickoff.date() for f in build_calendar(random.Random(1), SMALL))

    weekend = {n for d, n in per_day.items() if d.weekday() >= 5}
    weekday = {n for d, n in per_day.items() if d.weekday() < 5}
    assert weekend == {SMALL.matches_weekend}
    assert weekday == {SMALL.matches_weekday}


# --- odds: Decimal, exactly 3 dp, in range -------------------------------------------------


def test_odds_are_exact_3dp_decimals_in_range(pop: Population) -> None:
    low, high = (Decimal(x).scaleb(-3) for x in SMALL.odds_millis)

    for b in pop.bets:
        assert type(b.odds) is Decimal
        assert b.odds.as_tuple().exponent == -3
        assert low <= b.odds <= high


def test_draw_odds_never_has_float_noise() -> None:
    rng = random.Random(3)

    values = [draw_odds(rng, SMALL) for _ in range(10_000)]

    # Every value is exactly k/1000: str() shows 3 decimals and nothing like 2.1499999.
    assert all(len(str(v).split(".")[1]) == 3 for v in values)


# --- I7 rules (the cross-table part lives here, per the S1 principle) ---------------------


def test_deposit_and_bet_currency_match_the_account(pop: Population) -> None:
    currency = {a.id: a.currency for a in pop.accounts}

    assert all(d.currency == currency[d.account_id] for d in pop.deposits)
    assert all(b.currency == currency[b.account_id] for b in pop.bets)


def test_settlement_amounts_follow_status(pop: Population) -> None:
    for b in pop.bets:
        if b.status == "lost":
            assert b.payout_minor == 0
        elif b.status == "void":
            assert b.payout_minor == b.stake_minor
        elif b.status == "won":
            assert b.payout_minor == int(Decimal(b.stake_minor) * b.odds)
        else:
            assert b.settled_at is None and b.payout_minor is None


# --- realism: loose bands, so a config typo shows up --------------------------------------


def test_outcome_shares_are_realistic(pop: Population) -> None:
    settled = [b for b in pop.bets if b.status != "open"]
    share = Counter(b.status for b in settled)
    n = len(settled)

    assert 0.30 < share["won"] / n < 0.50  # ~0.95/odds averaged over 1.2-6.0
    assert share["void"] / n < 0.05
    stakes = sum(b.stake_minor for b in settled if b.status != "void")
    payouts = sum(b.payout_minor or 0 for b in settled if b.status != "void")
    assert 0.85 < payouts / stakes < 1.05  # the house keeps a few percent


def test_bets_on_upcoming_matches_are_still_open(pop: Population) -> None:
    open_bets = [b for b in pop.bets if b.status == "open"]

    assert open_bets, "a live snapshot has open bets on matches not yet played"
    last_chance = SMALL.end - timedelta(hours=SMALL.bet_lead_hours[1])
    assert all(b.placed_at > last_chance for b in open_bets)


def test_single_currency_aud_book(pop: Population) -> None:
    assert {(a.country, a.currency) for a in pop.accounts} == {("AU", "AUD")}
    assert {d.currency for d in pop.deposits} | {b.currency for b in pop.bets} == {"AUD"}


def test_money_sizes_respect_the_configured_minimums(pop: Population) -> None:
    assert min(d.amount_minor for d in pop.deposits) >= SMALL.deposit_min * 100
    assert min(b.stake_minor for b in pop.bets) >= SMALL.stake_min * 100
    assert all(d.amount_minor % 100 == 0 for d in pop.deposits)  # whole dollars


def test_every_status_appears_and_active_dominates(pop: Population) -> None:
    assert {a.status for a in pop.accounts} <= {"active", "suspended", "closed"}
    assert Counter(a.status for a in pop.accounts).most_common(1)[0][0] == "active"
