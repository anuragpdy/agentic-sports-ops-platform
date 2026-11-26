"""Planted stories: two fraud stories (F1, F2) and their innocent look-alikes (L1, L2).

A planted account is built with the SAME building blocks as an ordinary customer (signup,
status mix, deposit amounts and methods, kickoff times, background activity before and
after) and differs ONLY in one episode. Signals (table in docs/cards/simulator.md):

  N new account · D deposit burst · B big stake (>= A$200) · O long odds (>= 8.0)
  W wake-up after a break · J stake jump (>= 5x the account's own median)

  F1 = N + D + B + O         L1 = D + at most one of {N, B, O, J}
  F2 = W + J + O             L2 = W + at most one of {J, O}

So every fraud signal also shows up in some look-alikes; only the full combination is fraud.
Episode odds come from `draw_odds` (never the ordinary 1% long shots) so a look-alike can't
pick up a second fraud signal by chance.

The registry (`PlantedStory`) is the answer key's source. It stays in memory: S5 turns it
into alert_labels; the alert rules (S4) never receive it (D7).
"""

import random
import statistics
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.schemas.create import AccountCreate, BetCreate
from app.sim.config import START, SimConfig
from app.sim.fixtures import Fixture
from app.sim.population import (
    FixtureIndex,
    Population,
    add_activity,
    add_deposit_burst,
    draw_long_odds,
    draw_odds,
    draw_stake,
    draw_typical_stake,
    make_deposit,
    new_account,
    place_bet,
    random_time,
    scaled_count,
    to_minor,
)

Story = Literal["F1", "L1", "F2", "L2"]
Signal = Literal["new_account", "deposit_burst", "big_stake", "long_odds", "wake_up", "stake_jump"]

F1_SIGNALS: frozenset[Signal] = frozenset(
    {"new_account", "deposit_burst", "big_stake", "long_odds"}
)
F2_SIGNALS: frozenset[Signal] = frozenset({"wake_up", "stake_jump", "long_odds"})
L1_BORROW: tuple[Signal | None, ...] = (
    None,
    "new_account",
    "big_stake",
    "long_odds",
    "stake_jump",
)
L2_BORROW: tuple[Signal | None, ...] = (None, "stake_jump", "long_odds")


@dataclass(frozen=True)
class PlantedStory:
    account_id: uuid.UUID
    story: Story
    episode_start: datetime  # first episode row
    episode_end: datetime  # last episode row
    signals: frozenset[Signal]  # what was planted (tests re-measure it from the rows)


@dataclass(frozen=True)
class StoryCounts:
    fraud: int  # accounts per fraud story
    lookalike: int  # accounts per look-alike story

    @property
    def planted(self) -> int:
        return 2 * (self.fraud + self.lookalike)


def story_counts(cfg: SimConfig) -> StoryCounts:
    """Accounts per story; refuses an `accounts` too small to stay mostly ordinary (D1)."""
    counts = StoryCounts(
        fraud=max(cfg.min_per_story, round(cfg.accounts * cfg.fraud_share)),
        lookalike=max(cfg.min_per_story, round(cfg.accounts * cfg.lookalike_share)),
    )
    if counts.planted > cfg.accounts * cfg.max_planted_share:
        need = int(counts.planted / cfg.max_planted_share)
        raise ValueError(
            f"{cfg.accounts} accounts is too few: the stories need {counts.planted} planted "
            f"accounts (min_per_story={cfg.min_per_story}), which must be at most "
            f"{cfg.max_planted_share:.0%} of all accounts. Use at least {need} accounts."
        )
    return counts


def quota[T](rng: random.Random, n: int, options: Sequence[T]) -> list[T]:
    """Exactly balanced assignment (n items cycling through options), shuffled.

    Quotas instead of independent draws: every option appears even in a small test run,
    without depending on the luck of the seed.
    """
    items = [options[i % len(options)] for i in range(n)]
    rng.shuffle(items)
    return items


def tenths(share: float) -> list[bool]:
    """A share as ten booleans (0.8 -> 8 True, 2 False), for `quota`."""
    k = round(share * 10)
    return [True] * k + [False] * (10 - k)


def with_borrowed(base: Signal, borrowed: Signal | None) -> frozenset[Signal]:
    return frozenset({base} if borrowed is None else {base, borrowed})


def plant_stories(
    rng: random.Random, cfg: SimConfig, fixtures: FixtureIndex, pop: Population
) -> list[PlantedStory]:
    counts = story_counts(cfg)
    registry: list[PlantedStory] = []
    for weekend in quota(rng, counts.fraud, tenths(cfg.weekend_share_f1)):
        registry.append(plant_f1(rng, cfg, fixtures, pop, weekend))
    for borrowed, weekend in zip(
        quota(rng, counts.lookalike, L1_BORROW),
        quota(rng, counts.lookalike, tenths(cfg.weekend_share_l1)),
        strict=True,
    ):
        registry.append(plant_l1(rng, cfg, fixtures, pop, borrowed, weekend))
    for _ in range(counts.fraud):
        registry.append(plant_wake(rng, cfg, fixtures, pop, "F2", F2_SIGNALS, high_roller=False))
    for borrowed, high_roller in zip(
        quota(rng, counts.lookalike, L2_BORROW),
        quota(rng, counts.lookalike, tenths(cfg.l2_high_roller_share)),
        strict=True,
    ):
        signals = with_borrowed("wake_up", borrowed)
        registry.append(plant_wake(rng, cfg, fixtures, pop, "L2", signals, high_roller))
    return registry


# --- F1 / L1: a burst of deposits before a match ----------------------------------------


def plant_f1(
    rng: random.Random, cfg: SimConfig, fixtures: FixtureIndex, pop: Population, weekend: bool
) -> PlantedStory:
    target, burst_end = _burst_before_match(rng, cfg, fixtures, weekend)
    account = _add_account(rng, cfg, pop, _new_signup(rng, cfg, burst_end))
    typical = draw_typical_stake(rng, cfg)
    first = add_deposit_burst(
        rng, cfg, pop, account, burst_end, cfg.f1_burst_deposits, cfg.f1_burst_minutes
    )
    big = place_bet(
        rng,
        cfg,
        account,
        target,
        burst_end + timedelta(minutes=5),
        burst_end + timedelta(minutes=45),
        rng.randint(*cfg.f1_big_stake) * 100,
        draw_long_odds(rng, cfg.f1_odds_millis),
    )
    pop.bets.append(big)
    _background(rng, cfg, fixtures, pop, account, typical, first, big.placed_at)
    return PlantedStory(account.id, "F1", first, big.placed_at, F1_SIGNALS)


def plant_l1(
    rng: random.Random,
    cfg: SimConfig,
    fixtures: FixtureIndex,
    pop: Population,
    borrowed: Signal | None,
    weekend: bool,
) -> PlantedStory:
    target, burst_end = _burst_before_match(rng, cfg, fixtures, weekend)
    if borrowed == "new_account":
        signup = _new_signup(rng, cfg, burst_end)
    else:
        signup = random_time(
            rng,
            START - timedelta(days=cfg.history_days),
            burst_end - timedelta(days=cfg.established_days),
        )
    account = _add_account(rng, cfg, pop, signup)
    high_roller = borrowed == "big_stake"
    typical = draw_typical_stake(rng, cfg, cfg.high_roller_stake_median if high_roller else None)
    first = add_deposit_burst(
        rng, cfg, pop, account, burst_end, cfg.l1_burst_deposits, cfg.l1_burst_minutes
    )

    # 2-4 bets on that day's matches; the borrowed signal (if any) goes on the first one.
    # Bursts end by ~10:00 UTC and kickoffs stop at 11:30, so +12 h stays on the same day.
    day_matches = fixtures.between(
        burst_end + timedelta(minutes=65), burst_end + timedelta(hours=12)
    )
    bets: list[BetCreate] = []
    for i in range(rng.randint(*cfg.l1_bets)):
        stake = draw_stake(rng, cfg, typical)
        odds = draw_odds(rng, cfg)
        if i == 0 and borrowed == "big_stake":
            stake = rng.randint(*cfg.l1_big_stake) * 100
        if i == 0 and borrowed == "stake_jump":
            stake = to_minor(typical * rng.uniform(*cfg.l1_jump), cfg.stake_min)
        if i == 0 and borrowed == "long_odds":
            odds = draw_long_odds(rng, cfg.l1_odds_millis)
        fixture = rng.choice(day_matches)
        latest = burst_end + timedelta(minutes=60)
        bets.append(place_bet(rng, cfg, account, fixture, burst_end, latest, stake, odds))
    pop.bets.extend(bets)
    end = max(b.placed_at for b in bets)
    _background(rng, cfg, fixtures, pop, account, typical, first, end)
    return PlantedStory(account.id, "L1", first, end, with_borrowed("deposit_burst", borrowed))


def _burst_before_match(
    rng: random.Random, cfg: SimConfig, fixtures: FixtureIndex, weekend: bool
) -> tuple[Fixture, datetime]:
    """A match on a random (weekend or weekday) day, and a burst end 105-240 min before it.

    105 min leaves room for bets placed up to 45 min after the burst while still being at
    least lead_min (1 h) before kickoff.
    """
    days = [
        d
        for d in range(cfg.new_account_days + 1, cfg.days - 3)
        if ((START + timedelta(days=d)).weekday() >= 5) == weekend
    ]
    day = START + timedelta(days=rng.choice(days))
    target = rng.choice(fixtures.between(day, day + timedelta(days=1)))
    return target, target.kickoff - timedelta(minutes=rng.randint(105, 240))


def _new_signup(rng: random.Random, cfg: SimConfig, burst_end: datetime) -> datetime:
    """Signal N: account opened 0..new_account_days days before the episode."""
    return random_time(
        rng, burst_end - timedelta(days=cfg.new_account_days), burst_end - timedelta(hours=1)
    )


# --- F2 / L2: back after a long silence ---------------------------------------------------


def plant_wake(
    rng: random.Random,
    cfg: SimConfig,
    fixtures: FixtureIndex,
    pop: Population,
    story: Literal["F2", "L2"],
    signals: frozenset[Signal],
    high_roller: bool,
) -> PlantedStory:
    """F2 (wake-up + jump + long odds) or L2 (wake-up + at most one of jump / long odds).

    F2 jumps and long odds are stronger than L2's borrowed ones (see SimConfig).
    """
    day = rng.randint(cfg.wake_earliest_day, cfg.days - 3)
    start = random_time(rng, START + timedelta(days=day), START + timedelta(days=day, hours=12))
    gap_start = start - timedelta(days=rng.randint(*cfg.wake_gap_days))
    signup = random_time(rng, START - timedelta(days=cfg.history_days), START - timedelta(days=30))
    account = _add_account(rng, cfg, pop, signup)
    typical = draw_typical_stake(rng, cfg, cfg.high_roller_stake_median if high_roller else None)

    # History before the silence: at least one deposit and one bet.
    history = _activity(rng, cfg, fixtures, pop, account, typical, START, gap_start, None, 1)
    stakes = [b.stake_minor for b in history]
    median, peak = statistics.median(stakes), max(stakes)

    # The return: 1-2 deposits, then 2-4 bets over the next 3 days.
    deposit_times = sorted(
        [start]
        + [
            random_time(rng, start, start + timedelta(hours=6))
            for _ in range(rng.randint(*cfg.wake_deposits) - 1)
        ]
    )
    for t in deposit_times:
        pop.deposits.append(make_deposit(rng, cfg, account, t))
    lead_min = timedelta(hours=cfg.bet_lead_hours[0])
    matches = fixtures.between(start + lead_min, start + timedelta(days=3))
    fraud = story == "F2"
    jump = (cfg.f2_jump if fraud else cfg.l2_jump) if "stake_jump" in signals else None
    long_millis = (
        (cfg.f2_odds_millis if fraud else cfg.l2_odds_millis) if "long_odds" in signals else None
    )
    bets: list[BetCreate] = []
    for i in range(rng.randint(*cfg.wake_bets)):
        if jump is not None:  # signal J: stakes far above the account's own history
            stake = to_minor(median / 100 * rng.uniform(*jump), cfg.stake_min)
        else:  # back at their own old level: between their median and their peak
            stake = to_minor(rng.uniform(median, peak) / 100, cfg.stake_min)
        odds = draw_odds(rng, cfg)
        if i == 0 and long_millis is not None:  # signal O
            odds = draw_long_odds(rng, long_millis)
        fixture = rng.choice(matches)
        bets.append(
            place_bet(rng, cfg, account, fixture, start, start + timedelta(days=3), stake, odds)
        )
    pop.bets.extend(bets)
    end = max([b.placed_at for b in bets] + deposit_times)
    _activity(rng, cfg, fixtures, pop, account, typical, end, cfg.end, end, 0)
    return PlantedStory(account.id, story, start, end, signals)


# --- shared ----------------------------------------------------------------------------------


def _add_account(
    rng: random.Random, cfg: SimConfig, pop: Population, created_at: datetime
) -> AccountCreate:
    account = new_account(rng, cfg, created_at)
    pop.accounts.append(account)
    return account


def _background(
    rng: random.Random,
    cfg: SimConfig,
    fixtures: FixtureIndex,
    pop: Population,
    account: AccountCreate,
    typical: float,
    episode_start: datetime,
    episode_end: datetime,
) -> None:
    """Ordinary activity before and after the episode (same generator as everyone else)."""
    before = max(account.created_at, START)
    _activity(rng, cfg, fixtures, pop, account, typical, before, episode_start, None, 0)
    _activity(rng, cfg, fixtures, pop, account, typical, episode_end, cfg.end, episode_end, 0)


def _activity(
    rng: random.Random,
    cfg: SimConfig,
    fixtures: FixtureIndex,
    pop: Population,
    account: AccountCreate,
    typical: float,
    start: datetime,
    end: datetime,
    money_from: datetime | None,
    minimum: int,
) -> list[BetCreate]:
    """Ordinary activity in [start, end), counts scaled to the span's share of the window,
    so a planted account is about as active overall as an ordinary one."""
    if end <= start:
        return []
    share = (end - start) / (cfg.end - max(account.created_at, START))
    return add_activity(
        rng,
        cfg,
        fixtures,
        pop,
        account,
        start=start,
        end=end,
        typical_stake=typical,
        n_deposits=scaled_count(rng, cfg.deposits_per_account, share, minimum),
        n_bets=scaled_count(rng, cfg.bets_per_account, share, minimum),
        money_from=money_from,
    )
