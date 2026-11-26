"""Measure the six story signals from the generated ROWS (not from the registry).

Tests use this to check that what the registry says was planted is really in the data,
and that no single signal separates a fraud story from its look-alikes;
scripts/sim_report.py uses it to count ordinary accounts that look like fraud. Thresholds
match the docs/cards/simulator.md table. An evaluation tool: the alert rules never import
it (tests/test_sim_rules.py checks).
"""

import statistics
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from app.schemas.create import AccountCreate, BetCreate, DepositCreate
from app.sim.population import Population
from app.sim.stories import PlantedStory, Signal

NEW_ACCOUNT_DAYS = 14
BURST_COUNT, BURST_WINDOW = 3, timedelta(minutes=60)
BIG_STAKE_MINOR = 200 * 100
LONG_ODDS = Decimal("8.000")
QUIET_DAYS = 45
JUMP = 5


class Rows:
    """The population indexed by account, for per-account signal checks."""

    def __init__(self, pop: Population) -> None:
        self.accounts: dict[uuid.UUID, AccountCreate] = {a.id: a for a in pop.accounts}
        self.deposits: dict[uuid.UUID, list[DepositCreate]] = defaultdict(list)
        self.bets: dict[uuid.UUID, list[BetCreate]] = defaultdict(list)
        for d in pop.deposits:
            self.deposits[d.account_id].append(d)
        for b in pop.bets:
            self.bets[b.account_id].append(b)


def measure(rows: Rows, story: PlantedStory) -> set[Signal]:
    start, end = story.episode_start, story.episode_end
    account = rows.accounts[story.account_id]
    deposits = rows.deposits[story.account_id]
    bets = rows.bets[story.account_id]
    ep_deposits = sorted(d.created_at for d in deposits if start <= d.created_at <= end)
    ep_bets = [b for b in bets if start <= b.placed_at <= end]
    before = [b for b in bets if b.placed_at < start]
    found: set[Signal] = set()

    if account.created_at >= start - timedelta(days=NEW_ACCOUNT_DAYS):
        found.add("new_account")
    if any(
        ep_deposits[i + BURST_COUNT - 1] - ep_deposits[i] <= BURST_WINDOW
        for i in range(len(ep_deposits) - BURST_COUNT + 1)
    ):
        found.add("deposit_burst")
    if any(b.stake_minor >= BIG_STAKE_MINOR for b in ep_bets):
        found.add("big_stake")
    if any(b.odds >= LONG_ODDS for b in ep_bets):
        found.add("long_odds")
    quiet_from = start - timedelta(days=QUIET_DAYS)
    active_while_quiet = any(quiet_from <= d.created_at < start for d in deposits) or any(
        quiet_from <= b.placed_at < start for b in bets
    )
    if before and not active_while_quiet:
        found.add("wake_up")
    if before and ep_bets:
        median = statistics.median(b.stake_minor for b in before)
        if max(b.stake_minor for b in ep_bets) >= JUMP * median:
            found.add("stake_jump")
    return found
