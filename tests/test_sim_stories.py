"""S3: planted fraud stories and look-alikes. In memory, no database.

Signals are re-measured from the rows (app.sim.signals), so these tests check the
data an alert rule or an agent would actually see, not just what the registry claims.
"""

from collections import Counter

import pytest

from app.sim.build import SimResult, generate
from app.sim.config import START, SimConfig
from app.sim.signals import Rows, measure
from app.sim.stories import F1_SIGNALS, F2_SIGNALS, PlantedStory, Signal, Story

# 10 per fraud story, 12 per look-alike: every L1/L2 quota option appears 2-4 times.
CFG = SimConfig(accounts=400, min_per_story=10)
PAIRS: list[tuple[Story, Story, frozenset[Signal]]] = [
    ("F1", "L1", F1_SIGNALS),
    ("F2", "L2", F2_SIGNALS),
]
ALL_SIGNALS: tuple[Signal, ...] = (
    "new_account",
    "deposit_burst",
    "big_stake",
    "long_odds",
    "wake_up",
    "stake_jump",
)


@pytest.fixture(scope="module")
def result() -> SimResult:
    return generate(42, CFG)


@pytest.fixture(scope="module")
def measured(result: SimResult) -> dict[Story, list[set[Signal]]]:
    rows = Rows(result.population)
    by_story: dict[Story, list[set[Signal]]] = {"F1": [], "L1": [], "F2": [], "L2": []}
    for story in result.registry:
        by_story[story.story].append(measure(rows, story))
    return by_story


def _share(signal: Signal, accounts: list[set[Signal]]) -> float:
    return sum(signal in found for found in accounts) / len(accounts)


# --- registry ---------------------------------------------------------------------------------


def test_registry_has_the_configured_number_of_each_story(result: SimResult) -> None:
    assert Counter(s.story for s in result.registry) == {"F1": 10, "F2": 10, "L1": 12, "L2": 12}


def test_each_planted_story_is_its_own_account_in_the_population(result: SimResult) -> None:
    planted = [s.account_id for s in result.registry]
    accounts = {a.id for a in result.population.accounts}

    assert len(set(planted)) == len(planted)
    assert set(planted) <= accounts
    assert len(accounts) == CFG.accounts  # planted accounts replace ordinary ones


def test_episode_windows_lie_inside_the_simulated_period(result: SimResult) -> None:
    for s in result.registry:
        assert START <= s.episode_start <= s.episode_end < CFG.end


def test_too_few_accounts_is_refused_with_a_clear_message() -> None:
    # 4 stories x 50 = 200 planted, but at most half of all accounts may be planted.
    with pytest.raises(ValueError, match=r"200 accounts is too few.*Use at least 400"):
        generate(42, SimConfig(accounts=200, min_per_story=50))


def test_default_size_meets_the_per_story_minimum() -> None:
    from app.sim.stories import story_counts

    counts = story_counts(SimConfig())

    assert (counts.fraud, counts.lookalike) == (100, 150)  # 2% / 3% of 5,000, both >= 50


# --- planted signals are really in the data ---------------------------------------------------


@pytest.mark.parametrize("story", ["F1", "L1", "F2", "L2"])
def test_every_planted_signal_is_measurable_in_the_rows(result: SimResult, story: Story) -> None:
    rows = Rows(result.population)

    for s in (s for s in result.registry if s.story == story):
        missing = s.signals - measure(rows, s)
        assert not missing, f"{s.story} {s.account_id}: planted but not in rows: {missing}"


# --- D7: only the combination points to fraud ------------------------------------------------


@pytest.mark.parametrize(("fraud", "lookalike", "signature"), PAIRS, ids=["F1-L1", "F2-L2"])
def test_every_fraud_account_shows_the_full_combination(
    measured: dict[Story, list[set[Signal]]],
    fraud: Story,
    lookalike: Story,
    signature: frozenset[Signal],
) -> None:
    assert all(signature <= found for found in measured[fraud])


@pytest.mark.parametrize(("fraud", "lookalike", "signature"), PAIRS, ids=["F1-L1", "F2-L2"])
def test_no_lookalike_shows_the_full_combination(
    measured: dict[Story, list[set[Signal]]],
    fraud: Story,
    lookalike: Story,
    signature: frozenset[Signal],
) -> None:
    assert not any(signature <= found for found in measured[lookalike])


@pytest.mark.parametrize(("fraud", "lookalike", "signature"), PAIRS, ids=["F1-L1", "F2-L2"])
def test_no_single_signal_separates_fraud_from_its_lookalikes(
    measured: dict[Story, list[set[Signal]]],
    fraud: Story,
    lookalike: Story,
    signature: frozenset[Signal],
) -> None:
    # Any signal common among the fraud accounts (including incidental ones, e.g. F2's
    # stakes often clearing A$200) must also show up in a real share of look-alikes.
    for signal in ALL_SIGNALS:
        if _share(signal, measured[fraud]) >= 0.5:
            assert _share(signal, measured[lookalike]) >= 0.15, (
                f"{signal} alone separates {fraud} from {lookalike}"
            )


@pytest.mark.parametrize(("fraud", "lookalike", "signature"), PAIRS, ids=["F1-L1", "F2-L2"])
def test_fraud_signals_are_shared_out_across_lookalikes(
    measured: dict[Story, list[set[Signal]]],
    fraud: Story,
    lookalike: Story,
    signature: frozenset[Signal],
) -> None:
    # Each look-alike carries at most one signal it doesn't need for its own story.
    base: dict[Story, Signal] = {"L1": "deposit_burst", "L2": "wake_up"}
    for found in measured[lookalike]:
        assert base[lookalike] in found
        assert len((found & signature) - {base[lookalike]}) <= 1


# --- same generators: planted accounts differ only in the episode -----------------------------


def test_episode_days_mix_weekends_and_weekdays(result: SimResult) -> None:
    for story in ("F1", "L1"):
        weekend = {s.episode_start.weekday() >= 5 for s in result.registry if s.story == story}
        assert weekend == {True, False}, f"{story} episodes only on {weekend}"


def test_planted_accounts_have_ordinary_activity_outside_the_episode(result: SimResult) -> None:
    rows = Rows(result.population)

    def outside(s: PlantedStory) -> bool:
        return any(
            not s.episode_start <= b.placed_at <= s.episode_end for b in rows.bets[s.account_id]
        )

    share = sum(outside(s) for s in result.registry) / len(result.registry)
    assert share > 0.9  # not just a one-off episode on an otherwise empty account
