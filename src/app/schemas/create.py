"""Create models: the typed shape of rows BEFORE they are written to the database.

Every writer (the M3 simulator now, case actions in M5) builds rows through these, so bad
values fail here with a clear message instead of being silently changed by Postgres.
They close two M2 gaps (docs/specs/m03-simulator.md D4, D5):
- I5: odds are NUMERIC(8,3), and Postgres would round 2.1505 to 2.151. `Odds` rejects any
  value that rounding to 3 dp would change, and any value that doesn't fit NUMERIC(8,3).
  2.1500 is accepted: it is the same number as 2.150.
- I6: a naive datetime would be stored as if it were UTC. `UtcDatetime` rejects naive times
  and times whose offset is not zero (all stored times are UTC by convention).

Config: same as the read models (strict, frozen) plus extra="forbid", so a misspelt field
name is an error instead of being dropped. IDs have no default: the simulator draws them
from its seeded generator (D3), never uuid4().

Principle: Python guards what the database can't; the database guards the rest. So value
rules the database already enforces (amount > 0, odds > 1, ISO codes …) are not repeated
here, as in app.schemas.entities. One-row rules the database does NOT enforce (I7) live
here: a lost bet pays 0. Cross-table I7 rules (currency matches the account) need other
rows, so the simulator's tests check them. No CaseCreate yet: M5 builds it.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.values import (
    AccountStatus,
    AlertSeverity,
    BetStatus,
    DepositMethod,
    FraudLabel,
)


def _require_utc(value: datetime) -> datetime:
    # AwareDatetime has already rejected naive times; here only the offset is checked.
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"datetime must be in UTC (offset +00:00), got offset {value.utcoffset()}")
    return value


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]

# NUMERIC(8,3): at most 8 digits, 3 after the point. Pydantic ignores trailing zeros when
# counting places (2.1500 -> 3 places), which is exactly "reject if rounding would change it".
# It also rejects NaN and Infinity.
Odds = Annotated[Decimal, Field(max_digits=8, decimal_places=3)]


class CreateModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class AccountCreate(CreateModel):
    id: uuid.UUID
    country: str
    currency: str
    status: AccountStatus
    created_at: UtcDatetime


class DepositCreate(CreateModel):
    id: uuid.UUID
    account_id: uuid.UUID
    amount_minor: int
    currency: str
    method: DepositMethod
    created_at: UtcDatetime


class BetCreate(CreateModel):
    id: uuid.UUID
    account_id: uuid.UUID
    event_ref: str
    market: str
    selection: str
    stake_minor: int
    currency: str
    odds: Odds
    status: BetStatus
    placed_at: UtcDatetime
    settled_at: UtcDatetime | None
    payout_minor: int | None

    @model_validator(mode="after")
    def _lost_bet_pays_nothing(self) -> Self:
        # I7: the DB CHECK only ties settled_at/payout to "open"; it allows a lost bet with
        # a payout, or with payout NULL. Settled-and-lost means exactly 0.
        if self.status == "lost" and self.payout_minor != 0:
            raise ValueError(f"a lost bet must have payout_minor 0, got {self.payout_minor}")
        return self


class AlertCreate(CreateModel):
    id: uuid.UUID
    account_id: uuid.UUID
    case_id: uuid.UUID | None
    rule: str
    severity: AlertSeverity
    details: dict[str, Any]
    created_at: UtcDatetime


class AlertLabelCreate(CreateModel):
    alert_id: uuid.UUID
    label: FraudLabel
    scenario: str
    created_at: UtcDatetime
