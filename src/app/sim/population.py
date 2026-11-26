"""Ordinary customers: accounts, their deposits and their bets (no fraud, no alerts).

Every row is built through the create models (app.schemas.create), so a generator bug
(an odds value with 4 decimals, a naive datetime, a lost bet with a payout) fails here,
in memory, before anything reaches the database.
"""

import bisect
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from app.schemas.create import AccountCreate, BetCreate, DepositCreate
from app.schemas.values import BetStatus
from app.sim.config import START, SimConfig
from app.sim.fixtures import Fixture
from app.sim.ids import new_id

THOUSANDTH = Decimal("0.001")
SELECTIONS = ("home", "draw", "away")
MARKET = "match_result"


@dataclass
class Population:
    accounts: list[AccountCreate] = field(default_factory=list)
    deposits: list[DepositCreate] = field(default_factory=list)
    bets: list[BetCreate] = field(default_factory=list)


def random_time(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """A whole-second instant in [start, end). Whole seconds: no float microseconds."""
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=rng.randrange(max(span, 1)))


def draw_odds(rng: random.Random, cfg: SimConfig) -> Decimal:
    """Odds as Decimal from an integer number of thousandths: exact, never via a float."""
    low, high = cfg.odds_millis
    return Decimal(rng.randint(low, high)).scaleb(-3).quantize(THOUSANDTH)


def to_minor(major: float, minimum: int) -> int:
    """Whole dollars (at least `minimum`) -> cents. Stakes and deposits are round amounts."""
    return max(minimum, round(major)) * 100


def weighted[K: str](rng: random.Random, weights: dict[K, float]) -> K:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def settle(
    rng: random.Random, cfg: SimConfig, stake_minor: int, odds: Decimal, kickoff: datetime
) -> tuple[BetStatus, datetime | None, int | None]:
    """(status, settled_at, payout_minor). Matches after the window's end stay open."""
    settled_at = kickoff + timedelta(hours=cfg.settle_after_hours)
    if settled_at > cfg.end:
        return "open", None, None
    if rng.random() < cfg.void_share:
        return "void", settled_at, stake_minor  # void: stake refunded
    if rng.random() < float(Decimal(cfg.margin) / odds):
        payout = (Decimal(stake_minor) * odds).to_integral_value(rounding=ROUND_DOWN)
        return "won", settled_at, int(payout)
    return "lost", settled_at, 0


def make_bet(
    rng: random.Random,
    cfg: SimConfig,
    account: AccountCreate,
    fixture: Fixture,
    placed_at: datetime,
    stake_minor: int,
    odds: Decimal,
) -> BetCreate:
    status, settled_at, payout = settle(rng, cfg, stake_minor, odds, fixture.kickoff)
    return BetCreate(
        id=new_id(rng),
        account_id=account.id,
        event_ref=fixture.event_ref,
        market=MARKET,
        selection=rng.choice(SELECTIONS),
        stake_minor=stake_minor,
        currency=account.currency,  # I7: bet currency = account currency
        odds=odds,
        status=status,
        placed_at=placed_at,
        settled_at=settled_at,
        payout_minor=payout,
    )


class FixtureIndex:
    """Fixtures sorted by kickoff, for 'matches kicking off between a and b' lookups."""

    def __init__(self, calendar: list[Fixture]) -> None:
        self.fixtures = calendar
        self.kickoffs = [f.kickoff for f in calendar]

    def between(self, start: datetime, end: datetime) -> list[Fixture]:
        lo = bisect.bisect_left(self.kickoffs, start)
        hi = bisect.bisect_left(self.kickoffs, end)
        return self.fixtures[lo:hi]


def build_ordinary(
    rng: random.Random, cfg: SimConfig, fixtures: FixtureIndex, n: int
) -> Population:
    pop = Population()
    for _ in range(n):
        add_ordinary_customer(rng, cfg, fixtures, pop)
    return pop


def add_ordinary_customer(
    rng: random.Random, cfg: SimConfig, fixtures: FixtureIndex, pop: Population
) -> AccountCreate:
    account = new_account(rng, cfg, draw_signup(rng, cfg))
    pop.accounts.append(account)
    typical = draw_typical_stake(rng, cfg)
    add_activity(
        rng,
        cfg,
        fixtures,
        pop,
        account,
        start=max(account.created_at, START),
        end=cfg.end,
        typical_stake=typical,
        n_deposits=rng.randint(*cfg.deposits_per_account),
        n_bets=rng.randint(*cfg.bets_per_account),
    )
    return account


# --- building blocks, shared by ordinary customers and planted stories (app.sim.stories) ---


def draw_signup(rng: random.Random, cfg: SimConfig) -> datetime:
    return random_time(
        rng,
        START - timedelta(days=cfg.history_days),
        cfg.end - timedelta(days=cfg.last_signup_days),
    )


def new_account(rng: random.Random, cfg: SimConfig, created_at: datetime) -> AccountCreate:
    return AccountCreate(
        id=new_id(rng),
        country=cfg.country,
        currency=cfg.currency,
        status=weighted(rng, cfg.status_weights),  # same mix for everyone (D7)
        created_at=created_at,
    )


def draw_typical_stake(rng: random.Random, cfg: SimConfig, median: float | None = None) -> float:
    """A customer's typical stake (dollars). `median` overrides cfg.stake_median (high rollers)."""
    return (median or cfg.stake_median) * rng.lognormvariate(0, cfg.stake_profile_sigma)


def draw_stake(rng: random.Random, cfg: SimConfig, typical: float) -> int:
    """One bet's stake in cents, varying around the customer's typical stake."""
    return to_minor(typical * rng.lognormvariate(0, cfg.stake_bet_sigma), cfg.stake_min)


def draw_long_odds(rng: random.Random, millis: tuple[int, int]) -> Decimal:
    return Decimal(rng.randint(*millis)).scaleb(-3).quantize(THOUSANDTH)


def draw_ordinary_odds(rng: random.Random, cfg: SimConfig) -> Decimal:
    """Mostly 1.2-6.0; a small share of long shots, so long odds alone isn't suspicious."""
    if rng.random() < cfg.long_odds_share:
        return draw_long_odds(rng, cfg.long_odds_millis)
    return draw_odds(rng, cfg)


def make_deposit(
    rng: random.Random, cfg: SimConfig, account: AccountCreate, created_at: datetime
) -> DepositCreate:
    return DepositCreate(
        id=new_id(rng),
        account_id=account.id,
        amount_minor=to_minor(
            cfg.deposit_median * rng.lognormvariate(0, cfg.deposit_sigma), cfg.deposit_min
        ),
        currency=account.currency,  # I7: deposit currency = account currency
        method=weighted(rng, cfg.method_weights),
        created_at=created_at,
    )


def place_bet(
    rng: random.Random,
    cfg: SimConfig,
    account: AccountCreate,
    fixture: Fixture,
    earliest: datetime,
    latest: datetime,
    stake_minor: int,
    odds: Decimal,
) -> BetCreate:
    """A bet placed in [earliest, latest), clipped to lead_min..lead_max before kickoff."""
    lead_min, lead_max = (timedelta(hours=h) for h in cfg.bet_lead_hours)
    lo = max(earliest, fixture.kickoff - lead_max)
    hi = min(latest, fixture.kickoff - lead_min, cfg.end)
    placed_at = random_time(rng, lo, hi)
    return make_bet(rng, cfg, account, fixture, placed_at, stake_minor, odds)


def scaled_count(rng: random.Random, bounds: tuple[int, int], share: float, minimum: int) -> int:
    """A count from `bounds`, scaled to the share of the window an activity span covers."""
    return max(minimum, round(rng.randint(*bounds) * share))


def add_activity(
    rng: random.Random,
    cfg: SimConfig,
    fixtures: FixtureIndex,
    pop: Population,
    account: AccountCreate,
    *,
    start: datetime,
    end: datetime,
    typical_stake: float,
    n_deposits: int,
    n_bets: int,
    money_from: datetime | None = None,
) -> list[BetCreate]:
    """Ordinary behaviour in [start, end): deposits, then bets on upcoming matches.

    Bets need money: they come after `money_from` (default: the first deposit here).
    Matches up to lead_max after the window's end are allowed, so late bets stay open.
    Returns the bets added.
    """
    if end <= start:
        return []
    deposit_times = sorted(random_time(rng, start, end) for _ in range(n_deposits))
    for created_at in deposit_times:
        pop.deposits.append(make_deposit(rng, cfg, account, created_at))
    if money_from is None:
        if not deposit_times:
            return []
        money_from = deposit_times[0]
    lead_min, lead_max = (timedelta(hours=h) for h in cfg.bet_lead_hours)
    # Kickoff in [money_from + lead_min, end + lead_max): a valid placement time always exists.
    choices = fixtures.between(money_from + lead_min, min(end, cfg.end) + lead_max)
    if not choices:
        return []
    bets = []
    for _ in range(n_bets):
        fixture = rng.choice(choices)
        stake = draw_stake(rng, cfg, typical_stake)
        odds = draw_ordinary_odds(rng, cfg)
        bets.append(place_bet(rng, cfg, account, fixture, money_from, end, stake, odds))
    pop.bets.extend(bets)
    return bets
