"""S4: alert rules. Hand-made rows for each rule's threshold, then properties of a full run."""

import ast
import inspect
import random
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import app.sim.rules as rules_module
from app.schemas.create import AlertCreate, BetCreate, DepositCreate
from app.sim.build import SimResult, generate
from app.sim.config import SimConfig
from app.sim.rules import ESCALATE_ON, evaluate_rules
from tests.rows import T0, bet_row, deposit_row

ACCOUNT = uuid.UUID(int=1, version=4)
LABEL_WORDS = (
    "fraud",
    "benign",
    "lookalike",
    "look_alike",
    "story",
    "scenario",
    "label",
    "planted",
)


def _dep(minutes: float, amount: int = 50_00) -> DepositCreate:
    row = deposit_row(ACCOUNT, currency="AUD", amount_minor=amount, method="card")
    return DepositCreate.model_validate(row | {"created_at": T0 + timedelta(minutes=minutes)})


def _bet(minutes: float, stake: int = 10_00, odds: str = "2.000") -> BetCreate:
    row = bet_row(ACCOUNT, currency="AUD", stake_minor=stake, odds=Decimal(odds))
    return BetCreate.model_validate(row | {"placed_at": T0 + timedelta(minutes=minutes)})


def _run(deposits: list[DepositCreate], bets: list[BetCreate]) -> list[AlertCreate]:
    return evaluate_rules(random.Random(0), deposits, bets)


def _rules(alerts: list[AlertCreate]) -> list[str]:
    return [a.rule for a in alerts]


DAY = 24 * 60


# --- D7: the rules can't see the answer key -------------------------------------------------


def test_rules_module_imports_nothing_that_knows_the_labels() -> None:
    tree = ast.parse(Path(inspect.getfile(rules_module)).read_text())
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    allowed = {
        "random",
        "statistics",
        "uuid",
        "collections",
        "collections.abc",
        "dataclasses",
        "datetime",
        "decimal",
        "typing",
        "pydantic",
        "app.schemas.create",  # row shapes
        "app.schemas.values",  # allowed severities
        "app.sim.ids",  # seeded ids
    }

    assert imported <= allowed, f"rules.py imports {imported - allowed}"


def test_rules_take_only_rng_deposits_bets_and_thresholds() -> None:
    params = list(inspect.signature(evaluate_rules).parameters)

    assert params == ["rng", "deposits", "bets", "cfg"]


# --- each rule at its threshold --------------------------------------------------------------


def test_deposit_burst_fires_once_at_the_third_deposit_within_an_hour() -> None:
    alerts = _run([_dep(0), _dep(20), _dep(50), _dep(55), _dep(58)], [])

    assert _rules(alerts) == ["deposit_burst"]
    assert alerts[0].created_at == T0 + timedelta(minutes=50)
    assert alerts[0].details == {
        "deposits_in_window": 3,
        "span_minutes": 50,
        "total_minor": 150_00,
    }


def test_two_deposits_or_three_spread_over_more_than_an_hour_do_not_burst() -> None:
    assert _run([_dep(0), _dep(10)], []) == []
    assert _run([_dep(0), _dep(40), _dep(61)], []) == []


@pytest.mark.parametrize(
    ("stake", "expected"),
    [(199_00, []), (200_00, ["medium"]), (999_00, ["medium"]), (1_000_00, ["high"])],
)
def test_large_stake_threshold_and_severity(stake: int, expected: list[str]) -> None:
    alerts = _run([], [_bet(0, stake=stake)])

    assert [a.severity for a in alerts if a.rule == "large_stake"] == expected


@pytest.mark.parametrize(
    ("stake", "odds", "fires"),
    [(50_00, "8.000", True), (50_00, "7.999", False), (49_00, "20.000", False)],
)
def test_long_odds_stake_needs_both_long_odds_and_a_real_stake(
    stake: int, odds: str, fires: bool
) -> None:
    alerts = _run([], [_bet(0, stake=stake, odds=odds)])

    assert ("long_odds_stake" in _rules(alerts)) is fires
    if fires:
        assert alerts[0].details == {"stake_minor": stake, "odds_millis": int(Decimal(odds) * 1000)}


@pytest.mark.parametrize(("gap_days", "fires"), [(44, False), (45, True)])
def test_dormant_reactivation_fires_on_the_first_event_after_the_silence(
    gap_days: int, fires: bool
) -> None:
    alerts = _run([_dep(0), _dep(gap_days * DAY)], [_bet(0)])

    dormant = [a for a in alerts if a.rule == "dormant_reactivation"]
    assert bool(dormant) is fires
    if fires:
        assert dormant[0].created_at == T0 + timedelta(days=gap_days)
        assert dormant[0].details == {"days_inactive": gap_days, "prior_events": 2}


def test_a_brand_new_account_is_not_dormant() -> None:
    assert _run([_dep(0)], []) == []


@pytest.mark.parametrize(("stake", "fires"), [(49_00, False), (50_00, True)])
def test_stake_spike_is_relative_to_the_accounts_own_median(stake: int, fires: bool) -> None:
    history = [_bet(m, stake=10_00) for m in (0, 60, 120)]

    alerts = _run([], [*history, _bet(180, stake=stake)])

    assert ("stake_spike" in _rules(alerts)) is fires
    if fires:
        spike = next(a for a in alerts if a.rule == "stake_spike")
        assert spike.details == {"stake_minor": stake, "prior_median_minor": 10_00, "prior_bets": 3}


def test_stake_spike_needs_three_earlier_bets() -> None:
    alerts = _run([], [_bet(0), _bet(60), _bet(120, stake=150_00)])

    assert "stake_spike" not in _rules(alerts)


# --- de-duplication --------------------------------------------------------------------------


def test_repeats_inside_the_cooldown_are_dropped() -> None:
    bets = [_bet(d * DAY, stake=250_00) for d in (0, 2, 6)]

    assert _rules(_run([], bets)) == ["large_stake"]


def test_the_rule_fires_again_after_the_cooldown() -> None:
    bets = [_bet(0, stake=250_00), _bet(7 * DAY, stake=250_00)]

    assert _rules(_run([], bets)) == ["large_stake", "large_stake"]


def test_a_larger_stake_escalates_through_the_cooldown() -> None:
    # An ordinary A$220 bet must not hide a A$900 bet the next day.
    bets = [_bet(0, stake=220_00), _bet(DAY, stake=900_00), _bet(2 * DAY, stake=500_00)]

    stakes = [a.details["stake_minor"] for a in _run([], bets) if a.rule == "large_stake"]
    assert stakes == [220_00, 900_00]


# --- properties of a full run ----------------------------------------------------------------

CFG = SimConfig(accounts=400, min_per_story=10)


@pytest.fixture(scope="module")
def result() -> SimResult:
    return generate(42, CFG)


def test_every_alert_goes_through_alertcreate_with_no_case(result: SimResult) -> None:
    assert result.alerts
    assert all(type(a) is AlertCreate and a.case_id is None for a in result.alerts)


def test_alert_time_is_the_triggering_rows_time(result: SimResult) -> None:
    times: dict[uuid.UUID, set[datetime]] = defaultdict(set)
    for d in result.population.deposits:
        times[d.account_id].add(d.created_at)
    for b in result.population.bets:
        times[b.account_id].add(b.placed_at)

    assert all(a.created_at in times[a.account_id] for a in result.alerts)


def test_details_have_the_same_integer_keys_for_every_alert_of_a_rule(result: SimResult) -> None:
    keys: dict[str, set[frozenset[str]]] = defaultdict(set)
    for a in result.alerts:
        keys[a.rule].add(frozenset(a.details))
        assert all(type(v) is int for v in a.details.values()), a.details

    assert set(keys) == {
        "deposit_burst",
        "large_stake",
        "long_odds_stake",
        "dormant_reactivation",
        "stake_spike",
    }
    assert all(len(variants) == 1 for variants in keys.values()), keys


def test_no_label_words_anywhere_in_an_alert(result: SimResult) -> None:
    for a in result.alerts:
        text = f"{a.rule} {a.severity} {a.details}".lower()
        assert not any(word in text for word in LABEL_WORDS), text


def test_alerts_land_on_fraud_lookalikes_and_ordinary_customers(result: SimResult) -> None:
    story = {s.account_id: s.story for s in result.registry}
    groups = {story.get(a.account_id, "ordinary") for a in result.alerts}

    assert groups == {"F1", "F2", "L1", "L2", "ordinary"}


def test_every_fraud_episode_raises_at_least_one_alert_inside_it(result: SimResult) -> None:
    by_account: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    for a in result.alerts:
        by_account[a.account_id].append(a.created_at)

    for s in result.registry:
        if s.story in ("F1", "F2"):
            inside = [t for t in by_account[s.account_id] if s.episode_start <= t <= s.episode_end]
            assert inside, f"{s.story} {s.account_id}: no alert inside its episode"


def test_non_escalating_rules_never_repeat_within_the_cooldown(result: SimResult) -> None:
    last: dict[tuple[uuid.UUID, str], datetime] = {}
    for a in sorted(result.alerts, key=lambda a: a.created_at):
        key = (a.account_id, a.rule)
        if a.rule not in ESCALATE_ON and key in last:
            assert a.created_at - last[key] >= timedelta(days=7)
        last[key] = a.created_at


def test_same_seed_gives_identical_alerts(result: SimResult) -> None:
    again = generate(42, CFG)

    assert [a.model_dump() for a in again.alerts] == [a.model_dump() for a in result.alerts]


def test_alerts_do_not_depend_on_input_order(result: SimResult) -> None:
    deposits, bets = list(result.population.deposits), list(result.population.bets)
    random.Random(1).shuffle(deposits)
    random.Random(2).shuffle(bets)

    shuffled = evaluate_rules(random.Random(0), deposits, bets)
    original = evaluate_rules(random.Random(0), result.population.deposits, result.population.bets)
    assert [a.model_dump() for a in shuffled] == [a.model_dump() for a in original]
