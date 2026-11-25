"""Decide whether integration tests may run against TEST_DATABASE_URL.

A pure function (no pytest, no DB), so the rules themselves are unit-tested in
tests/test_db_guard.py:
- unset or empty locally   → skip (reason printed in the pytest summary)
- unset or empty in CI      → fail, so CI can never go green by silently skipping
- database name not *_test  → fail: these tests drop the whole schema
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.engine import URL

from app.db.url import sqlalchemy_url

UNSET_REASON = "TEST_DATABASE_URL is not set; see docs/specs/m02-data-model.md"


@dataclass(frozen=True)
class GuardDecision:
    action: Literal["run", "skip", "fail"]
    reason: str = ""
    url: URL | None = None


def decide(raw_url: str | None, app_env: str) -> GuardDecision:
    if not raw_url:  # None or "" (an empty `TEST_DATABASE_URL=` line in .env)
        if app_env == "ci":
            return GuardDecision("fail", f"{UNSET_REASON} (required in CI)")
        return GuardDecision("skip", f"{UNSET_REASON} (integration tests skipped)")

    url = sqlalchemy_url(raw_url)
    if not (url.database or "").endswith("_test"):
        return GuardDecision(
            "fail", f"refusing to run: database {url.database!r} does not end with '_test'"
        )
    return GuardDecision("run", url=url)
