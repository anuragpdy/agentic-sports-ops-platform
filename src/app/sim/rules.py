"""Alert rules: simple behaviour checks over deposits and bets (spec D2, D7).

Leakage guard (D7): this module sees ONLY deposits and bets. It does not import the
planted-story registry, the population builder or anything else that knows which accounts
are fraud (tests/test_sim_rules.py checks the imports). So alerts fire on fraud,
look-alikes and ordinary customers alike, purely from behaviour, which makes them noisy,
as real alerts are.

`details` holds evidence numbers only (integers: JSONB has no Decimal type, so odds are
stored as thousandths), with the same keys for every alert of a rule.

De-duplication: a cooldown per (account, rule). After a rule fires for an account, later
triggers of the same rule on that account within `cooldown_days` are dropped, with one
exception: the stake rules ESCALATE, i.e. a larger stake than the last alerted one fires
again. Without that, an ordinary A$220 bet could start a cooldown that swallows a A$900
bet the next day. (Bursts don't escalate: the 4th and 5th deposit of one burst would
re-fire. Dormancy can't repeat within a week.)
"""

import random
import statistics
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.create import AlertCreate, BetCreate, DepositCreate
from app.schemas.values import AlertSeverity
from app.sim.ids import new_id


class RuleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    burst_count: int = 3  # deposit_burst: this many deposits ...
    burst_minutes: int = 60  # ... within this many minutes
    large_stake_minor: int = 200_00  # large_stake: A$200
    large_stake_high_minor: int = 1_000_00  # A$1,000 -> high
    long_odds: Decimal = Decimal("8.000")  # long_odds_stake: odds at least this ...
    long_odds_stake_minor: int = 50_00  # ... with a stake of at least A$50
    dormant_days: int = 45  # dormant_reactivation: silent at least this long
    spike_ratio: int = 5  # stake_spike: stake >= 5x the median of ...
    spike_history: int = 20  # ... the account's last 20 bets
    spike_min_history: int = 3  # ... needing at least 3 earlier bets
    cooldown_days: int = 7


# Stake rules re-fire inside the cooldown when this evidence value beats the last alert's.
ESCALATE_ON = {
    "large_stake": "stake_minor",
    "long_odds_stake": "stake_minor",
    "stake_spike": "stake_minor",
}


@dataclass
class _Account:
    """Running state for one account while its events are replayed in time order."""

    deposits: list[tuple[datetime, int]] = field(default_factory=list)  # (time, amount)
    stakes: list[int] = field(default_factory=list)
    last_event: datetime | None = None
    events: int = 0
    last_fired: dict[str, tuple[datetime, int]] = field(default_factory=dict)  # (when, value)


def evaluate_rules(
    rng: random.Random,
    deposits: Iterable[DepositCreate],
    bets: Iterable[BetCreate],
    cfg: RuleConfig | None = None,
) -> list[AlertCreate]:
    """Replay each account's deposits and bets in time order and return the alerts."""
    cfg = cfg or RuleConfig()
    events: dict[uuid.UUID, list[DepositCreate | BetCreate]] = defaultdict(list)
    for d in deposits:
        events[d.account_id].append(d)
    for b in bets:
        events[b.account_id].append(b)

    alerts: list[AlertCreate] = []
    # Sorted account order and a total order on events: the output (and so the IDs drawn
    # from rng) doesn't depend on how the input lists happen to be ordered.
    for account_id in sorted(events):
        state = _Account()
        for event in sorted(events[account_id], key=_event_key):
            for rule, severity, details in _check(cfg, state, event):
                when = _time(event)
                value = details[ESCALATE_ON[rule]] if rule in ESCALATE_ON else 0
                if _suppressed(cfg, state.last_fired.get(rule), when, value):
                    continue
                state.last_fired[rule] = (when, value)
                alerts.append(
                    AlertCreate(
                        id=new_id(rng),
                        account_id=account_id,
                        case_id=None,
                        rule=rule,
                        severity=severity,
                        details=details,
                        created_at=when,
                    )
                )
            _update(state, event)
    return alerts


def _suppressed(
    cfg: RuleConfig, last: tuple[datetime, int] | None, when: datetime, value: int
) -> bool:
    """Inside the cooldown and not stronger than the last alert of this rule."""
    if last is None:
        return False
    last_when, last_value = last
    return when - last_when < timedelta(days=cfg.cooldown_days) and value <= last_value


def _time(event: DepositCreate | BetCreate) -> datetime:
    return event.created_at if isinstance(event, DepositCreate) else event.placed_at


def _event_key(event: DepositCreate | BetCreate) -> tuple[datetime, int, uuid.UUID]:
    # Same instant: the deposit comes first (money arrives, then it is staked).
    return _time(event), 0 if isinstance(event, DepositCreate) else 1, event.id


Fired = tuple[str, AlertSeverity, dict[str, Any]]


def _check(cfg: RuleConfig, state: _Account, event: DepositCreate | BetCreate) -> list[Fired]:
    """Rules that fire on this event, given the account's history BEFORE it."""
    fired: list[Fired] = []
    when = _time(event)

    if state.last_event is not None:
        silent = when - state.last_event
        if silent >= timedelta(days=cfg.dormant_days):
            fired.append(
                (
                    "dormant_reactivation",
                    "low",
                    {"days_inactive": silent.days, "prior_events": state.events},
                )
            )

    if isinstance(event, DepositCreate):
        window_start = when - timedelta(minutes=cfg.burst_minutes)
        recent = [d for d in state.deposits if d[0] >= window_start]
        recent.append((when, event.amount_minor))
        if len(recent) >= cfg.burst_count:
            span = int((when - recent[0][0]).total_seconds() // 60)
            total = sum(amount for _, amount in recent)
            fired.append(
                (
                    "deposit_burst",
                    "medium",  # fires at the 3rd deposit; the cooldown absorbs the rest
                    {"deposits_in_window": len(recent), "span_minutes": span, "total_minor": total},
                )
            )
        return fired

    odds_millis = int(event.odds * 1000)
    if event.stake_minor >= cfg.large_stake_minor:
        high = event.stake_minor >= cfg.large_stake_high_minor
        fired.append(
            (
                "large_stake",
                "high" if high else "medium",
                {"stake_minor": event.stake_minor, "odds_millis": odds_millis},
            )
        )
    if event.odds >= cfg.long_odds and event.stake_minor >= cfg.long_odds_stake_minor:
        fired.append(
            (
                "long_odds_stake",
                "low",
                {"stake_minor": event.stake_minor, "odds_millis": odds_millis},
            )
        )
    history = state.stakes[-cfg.spike_history :]
    if len(history) >= cfg.spike_min_history:
        median = int(statistics.median(history))
        if event.stake_minor >= cfg.spike_ratio * median:
            fired.append(
                (
                    "stake_spike",
                    "medium",
                    {
                        "stake_minor": event.stake_minor,
                        "prior_median_minor": median,
                        "prior_bets": len(history),
                    },
                )
            )
    return fired


def _update(state: _Account, event: DepositCreate | BetCreate) -> None:
    if isinstance(event, DepositCreate):
        state.deposits.append((event.created_at, event.amount_minor))
    else:
        state.stakes.append(event.stake_minor)
    state.last_event = _time(event)
    state.events += 1
