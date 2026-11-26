"""Top-level entry: seed + config -> all rows, in memory. S4-S5 extend this pipeline.

The ONLY place a Random is created: everything below receives this one instance (D3).
"""

import random
from dataclasses import dataclass

from app.sim.config import SimConfig
from app.sim.fixtures import build_calendar
from app.sim.population import FixtureIndex, Population, build_ordinary
from app.sim.stories import PlantedStory, plant_stories, story_counts


@dataclass
class SimResult:
    population: Population
    # In memory only: the source of alert_labels (S5); never given to the alert rules (D7).
    registry: list[PlantedStory]


def generate(seed: int, cfg: SimConfig) -> SimResult:
    counts = story_counts(cfg)  # fail fast, before any work, if accounts is too small
    rng = random.Random(seed)
    fixtures = FixtureIndex(build_calendar(rng, cfg))
    population = build_ordinary(rng, cfg, fixtures, cfg.accounts - counts.planted)
    registry = plant_stories(rng, cfg, fixtures, population)
    return SimResult(population, registry)
