"""Synthetic fixture calendar: the matches customers bet on (no external data, see spec D2).

Weekends have more matches than weekdays, which gives the "busy match day" the L1
look-alike needs (S3).
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.sim.config import START, SimConfig


@dataclass(frozen=True)
class Fixture:
    event_ref: str
    kickoff: datetime


def build_calendar(rng: random.Random, cfg: SimConfig) -> list[Fixture]:
    """Matches from START to a few days past the window's end, sorted by kickoff."""
    fixtures: list[Fixture] = []
    low, high = cfg.kickoff_hours
    for day in range(cfg.days + cfg.calendar_extra_days):
        date = START + timedelta(days=day)
        count = cfg.matches_weekend if date.weekday() >= 5 else cfg.matches_weekday
        for _ in range(count):
            kickoff = date + timedelta(hours=rng.randint(low, high), minutes=rng.choice((0, 30)))
            fixtures.append(Fixture(event_ref=f"fx-{len(fixtures):05d}", kickoff=kickoff))
    fixtures.sort(key=lambda f: (f.kickoff, f.event_ref))
    return fixtures
