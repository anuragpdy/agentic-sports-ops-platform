"""Seeded UUIDs (D3): same seed, same IDs. uuid4() would read the OS random source."""

import random
import uuid


def new_id(rng: random.Random) -> uuid.UUID:
    # version=4 sets the version/variant bits, so these look like ordinary v4 UUIDs.
    return uuid.UUID(int=rng.getrandbits(128), version=4)
