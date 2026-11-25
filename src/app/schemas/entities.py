"""Read models: the typed shape of each table's rows once they leave the database.

Later code (agent tools in M4, API responses) passes these around instead of raw rows.
Build one from a DB row or ORM object with `BetRead.model_validate(row)`.

Config choices:
- from_attributes: read fields from row/ORM attributes, not only from dicts.
- strict: no silent conversion. A float odds value, a Decimal amount or a string UUID is an
  error, not quietly converted, so a type mismatch in the DB layer can't hide here.
  (This is how "money stays int, odds stay Decimal" is guaranteed.)
- frozen: read models are snapshots; changing one is a bug, so it raises.
- AwareDatetime: a timestamp without a timezone is rejected (all times are UTC instants).

Allowed values come from app.schemas.values, the same Literals the DB CHECKs are built from.
Value rules (amount > 0, odds > 1 …) are NOT repeated here: the database enforces them, and
copying them would give two lists that can drift apart.
"""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.schemas.values import (
    AccountStatus,
    AlertSeverity,
    BetStatus,
    CaseStatus,
    DepositMethod,
    FraudLabel,
)


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, strict=True, frozen=True)


class AccountRead(ReadModel):
    id: uuid.UUID
    country: str
    currency: str
    status: AccountStatus
    created_at: AwareDatetime


class DepositRead(ReadModel):
    id: uuid.UUID
    account_id: uuid.UUID
    amount_minor: int
    currency: str
    method: DepositMethod
    created_at: AwareDatetime


class BetRead(ReadModel):
    id: uuid.UUID
    account_id: uuid.UUID
    event_ref: str
    market: str
    selection: str
    stake_minor: int
    currency: str
    odds: Decimal
    status: BetStatus
    placed_at: AwareDatetime
    settled_at: AwareDatetime | None
    payout_minor: int | None


class CaseRead(ReadModel):
    id: uuid.UUID
    status: CaseStatus
    opened_at: AwareDatetime
    closed_at: AwareDatetime | None
    resolution: str | None


class AlertRead(ReadModel):
    id: uuid.UUID
    account_id: uuid.UUID
    case_id: uuid.UUID | None
    rule: str
    severity: AlertSeverity
    details: dict[str, Any]
    created_at: AwareDatetime


class AlertLabelRead(ReadModel):
    """Ground truth. Never hand this to agent tools (enforced by a DB role in M4)."""

    alert_id: uuid.UUID
    label: FraudLabel
    scenario: str
    created_at: AwareDatetime
