"""Valid rows for every table, as dicts. Tests change one field to probe one rule."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, insert

from app.db.models import Account

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 1, 1, 14, 0, tzinfo=UTC)


def account_row(**overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "country": "IN",
        "currency": "INR",
        "status": "active",
        "created_at": T0,
    } | overrides


def deposit_row(account_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "amount_minor": 25075,
        "currency": "INR",
        "method": "upi",
        "created_at": T0,
    } | overrides


def bet_row(account_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "event_ref": "statsbomb:3869685",
        "market": "match_result",
        "selection": "home",
        "stake_minor": 10000,
        "currency": "INR",
        "odds": Decimal("2.150"),
        "status": "open",
        "placed_at": T0,
        "settled_at": None,
        "payout_minor": None,
    } | overrides


def case_row(**overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "status": "open",
        "opened_at": T0,
        "closed_at": None,
        "resolution": None,
    } | overrides


def alert_row(account_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "account_id": account_id,
        "case_id": None,
        "rule": "rapid_deposit_withdraw",
        "severity": "high",
        "details": {"deposits_24h": 7},
        "created_at": T0,
    } | overrides


def alert_label_row(alert_id: uuid.UUID, **overrides: Any) -> dict[str, Any]:
    return {
        "alert_id": alert_id,
        "label": "benign",
        "scenario": "lookalike",
        "created_at": T1,
    } | overrides


def add_account(db: Connection) -> uuid.UUID:
    row = account_row()
    db.execute(insert(Account), row)
    account_id: uuid.UUID = row["id"]
    return account_id
