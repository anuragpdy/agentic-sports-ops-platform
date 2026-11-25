"""Read models build from real Postgres rows, and the types survive the round trip.

Strict read models mean these tests fail if the driver ever hands back the wrong Python
type (e.g. a float for NUMERIC), rather than Pydantic quietly converting it.
"""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import Connection, insert, inspect, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Account, Alert, AlertLabel, Bet, Case, Deposit
from app.schemas.entities import (
    AccountRead,
    AlertLabelRead,
    AlertRead,
    BetRead,
    CaseRead,
    DepositRead,
)
from tests.rows import (
    T1,
    account_row,
    alert_label_row,
    alert_row,
    bet_row,
    case_row,
    deposit_row,
)

pytestmark = pytest.mark.integration


def _insert_and_read_back(db: Connection, model: type[Base], row: dict[str, Any]) -> Any:
    """Insert `row`, then fetch it with plain SQL (a Row, as agent tools will read it)."""
    db.execute(insert(model), row)
    table = model.__table__
    return db.execute(select(table).where(table.c[_pk(model)] == row[_pk(model)])).one()


def _pk(model: type[Base]) -> str:
    name: str = inspect(model).primary_key[0].name
    return name


def test_every_read_model_builds_from_a_db_row_unchanged(db: Connection) -> None:
    account = account_row()
    case = case_row(status="closed", closed_at=T1, resolution="benign")
    deposit = deposit_row(account["id"])
    bet = bet_row(account["id"], status="won", settled_at=T1, payout_minor=21500)
    alert = alert_row(account["id"], case_id=case["id"], details={"deposits_24h": 7, "ok": True})
    label = alert_label_row(alert["id"])

    cases: list[tuple[type[Base], dict[str, Any], type[BaseModel]]] = [
        (Account, account, AccountRead),
        (Case, case, CaseRead),
        (Deposit, deposit, DepositRead),
        (Bet, bet, BetRead),
        (Alert, alert, AlertRead),
        (AlertLabel, label, AlertLabelRead),
    ]
    for model, row, read_model in cases:
        db_row = _insert_and_read_back(db, model, row)

        built = read_model.model_validate(db_row)

        assert built.model_dump() == row, model.__tablename__


def test_money_stays_int_and_odds_stay_decimal(db: Connection) -> None:
    account = account_row()
    bet = bet_row(account["id"], status="won", settled_at=T1, payout_minor=21500)
    db.execute(insert(Account), account)

    read = BetRead.model_validate(_insert_and_read_back(db, Bet, bet))

    # `type(...) is` rather than isinstance: bool is an int subclass, and we want exact types.
    assert type(read.stake_minor) is int and read.stake_minor == 10000
    assert type(read.payout_minor) is int and read.payout_minor == 21500
    assert type(read.odds) is Decimal and read.odds == Decimal("2.150")
    assert read.placed_at.tzinfo is not None


def test_read_model_builds_from_an_orm_object(db: Connection) -> None:
    account = account_row()
    db.execute(insert(Account), account)
    deposit = deposit_row(account["id"])
    db.execute(insert(Deposit), deposit)

    with Session(bind=db) as session:
        orm_deposit = session.get(Deposit, deposit["id"])

        read = DepositRead.model_validate(orm_deposit)

    assert read.model_dump() == deposit
