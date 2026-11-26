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
    signup_from = START - timedelta(days=cfg.history_days)
    signup_to = cfg.end - timedelta(days=cfg.last_signup_days)
    account = AccountCreate(
        id=new_id(rng),
        country=cfg.country,
        currency=cfg.currency,
        status=weighted(rng, cfg.status_weights),
        created_at=random_time(rng, signup_from, signup_to),
    )
    pop.accounts.append(account)

    active_from = max(account.created_at, START)
    deposit_times = sorted(
        random_time(rng, active_from, cfg.end)
        for _ in range(rng.randint(*cfg.deposits_per_account))
    )
    for created_at in deposit_times:
        pop.deposits.append(
            DepositCreate(
                id=new_id(rng),
                account_id=account.id,
                amount_minor=to_minor(
                    cfg.deposit_median * rng.lognormvariate(0, cfg.deposit_sigma), cfg.deposit_min
                ),
                currency=account.currency,  # I7
                method=weighted(rng, cfg.method_weights),
                created_at=created_at,
            )
        )

    # Bets only after the first deposit (no money before that) and before the window ends,
    # placed lead_min..lead_max hours before kickoff. Matches up to lead_max after the end
    # are allowed: bets on them are still open in the snapshot, as in a live sportsbook.
    lead_min, lead_max = (timedelta(hours=h) for h in cfg.bet_lead_hours)
    first_deposit = deposit_times[0]
    choices = fixtures.between(first_deposit + lead_min, cfg.end + lead_max)
    if not choices:
        return account
    typical_stake = cfg.stake_median * rng.lognormvariate(0, cfg.stake_profile_sigma)
    for _ in range(rng.randint(*cfg.bets_per_account)):
        fixture = rng.choice(choices)
        # Never empty: the fixture kicks off in [first_deposit + lead_min, end + lead_max).
        earliest = max(first_deposit, fixture.kickoff - lead_max)
        latest = min(fixture.kickoff - lead_min, cfg.end)
        placed_at = random_time(rng, earliest, latest)
        stake = to_minor(typical_stake * rng.lognormvariate(0, cfg.stake_bet_sigma), cfg.stake_min)
        pop.bets.append(make_bet(rng, cfg, account, fixture, placed_at, stake, draw_odds(rng, cfg)))
    return account
