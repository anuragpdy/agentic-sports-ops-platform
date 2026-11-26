"""Top-level entry: seed + config -> all rows, in memory. S5 adds labels.

The ONLY place a Random is created: everything below receives this one instance (D3).
"""

import random
from dataclasses import dataclass

from app.schemas.create import AlertCreate
from app.sim.config import SimConfig
from app.sim.fixtures import build_calendar
from app.sim.population import FixtureIndex, Population, build_ordinary
from app.sim.rules import evaluate_rules
from app.sim.stories import PlantedStory, plant_stories, story_counts


@dataclass
class SimResult:
    population: Population
    # In memory only: the source of alert_labels (S5); never given to the alert rules (D7).
    registry: list[PlantedStory]
    alerts: list[AlertCreate]


def generate(seed: int, cfg: SimConfig) -> SimResult:
    counts = story_counts(cfg)  # fail fast, before any work, if accounts is too small
    rng = random.Random(seed)
    fixtures = FixtureIndex(build_calendar(rng, cfg))
    population = build_ordinary(rng, cfg, fixtures, cfg.accounts - counts.planted)
    registry = plant_stories(rng, cfg, fixtures, population)
    # D7: the rules get deposits and bets only, never the registry.
    alerts = evaluate_rules(rng, population.deposits, population.bets)
    return SimResult(population, registry, alerts)
