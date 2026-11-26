"""Seeded sportsbook simulator (docs/specs/m03-simulator.md).

Determinism (D3): one `random.Random(seed)` is created at the top and passed as the first
argument to every function. Nothing here reads the clock, the module-level `random`
functions or `uuid4()`, so the same seed always gives the same rows.
"""
