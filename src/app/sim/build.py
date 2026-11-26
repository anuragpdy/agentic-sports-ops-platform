"""Top-level entry: seed + config -> all rows, in memory. S3-S5 extend this pipeline.

The ONLY place a Random is created: everything below receives this one instance (D3).
"""

import random

from app.sim.config import SimConfig
from app.sim.fixtures import build_calendar
from app.sim.population import FixtureIndex, Population, build_ordinary


def generate(seed: int, cfg: SimConfig) -> Population:
    rng = random.Random(seed)
    fixtures = FixtureIndex(build_calendar(rng, cfg))
    return build_ordinary(rng, cfg, fixtures, cfg.accounts)
