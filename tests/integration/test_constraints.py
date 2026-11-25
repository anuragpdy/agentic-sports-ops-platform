"""The database itself rejects bad rows (spec: "database rules, not just Python rules").

Each rejection test asserts WHICH constraint fired (Postgres reports its name), not just that
some error happened: otherwise a test could pass because its base row was broken in another way.
"""

import uuid
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy import Connection, delete, insert
from sqlalchemy.exc import IntegrityError

from app.db.models import Account, Alert, AlertLabel, Bet, Case, Deposit
from tests.rows import (
    T1,
    account_row,
    add_account,
    alert_label_row,
    alert_row,
    bet_row,
    case_row,
    deposit_row,
)

pytestmark = pytest.mark.integration


def valid_row(db: Connection, model: type[Any]) -> dict[str, Any]:
    """A valid row for `model` whose status-like value can be swapped without breaking others."""
    if model is Account:
        return account_row()
    if model is Case:
        return case_row()
    if model is Deposit:
        return deposit_row(add_account(db))
    if model is Bet:
        # Settled, so a non-'open' status breaks only ck_bets_status_allowed. An open base
        # row would also break ck_bets_settlement_matches_status, and Postgres may report
        # either one.
        return bet_row(add_account(db), status="won", settled_at=T1, payout_minor=21500)
    raise ValueError(f"no valid row for {model}")


def violated(exc: pytest.ExceptionInfo[IntegrityError]) -> str | None:
    """Name of the constraint Postgres says was violated."""
    orig = exc.value.orig
    assert isinstance(orig, psycopg.Error)
    return orig.diag.constraint_name


# --- happy path: proves the base rows are valid ----------------------------------------


def test_valid_rows_in_every_table_are_accepted(db: Connection) -> None:
    account_id = add_account(db)
    case = case_row(status="closed", closed_at=T1, resolution="benign: salary deposit")
    alert = alert_row(account_id, case_id=case["id"])

    db.execute(insert(Case), case)
    db.execute(insert(Deposit), deposit_row(account_id))
    db.execute(insert(Bet), bet_row(account_id))
    db.execute(insert(Bet), bet_row(account_id, status="won", settled_at=T1, payout_minor=21500))
    db.execute(insert(Bet), bet_row(account_id, status="lost", settled_at=T1, payout_minor=0))
    db.execute(insert(Alert), alert)
    db.execute(insert(AlertLabel), alert_label_row(alert["id"]))


# --- spec rejections ---------------------------------------------------------------------


@pytest.mark.parametrize("amount", [-100, 0])
def test_rejects_deposit_amount_not_positive(db: Connection, amount: int) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Deposit), deposit_row(account_id, amount_minor=amount))

    assert violated(exc) == "ck_deposits_amount_positive"


@pytest.mark.parametrize("odds", [Decimal("1.000"), Decimal("0.500")])
def test_rejects_odds_not_above_one(db: Connection, odds: Decimal) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Bet), bet_row(account_id, odds=odds))

    assert violated(exc) == "ck_bets_odds_gt_one"


def test_rejects_deposit_for_missing_account(db: Connection) -> None:
    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Deposit), deposit_row(uuid.uuid4()))

    assert violated(exc) == "fk_deposits_account_id_accounts"


@pytest.mark.parametrize(
    ("model", "column", "value", "constraint"),
    [
        (Account, "status", "frozen", "ck_accounts_status_allowed"),
        (Case, "status", "archived", "ck_cases_status_allowed"),
        (Bet, "status", "cancelled", "ck_bets_status_allowed"),
        (Deposit, "method", "crypto", "ck_deposits_method_allowed"),
    ],
)
def test_rejects_unknown_allowed_value(
    db: Connection, model: type[Any], column: str, value: str, constraint: str
) -> None:
    row = valid_row(db, model) | {column: value}

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(model), row)

    assert violated(exc) == constraint


@pytest.mark.parametrize("currency", ["inr", "IN", "IN1"])
def test_rejects_currency_that_is_not_three_uppercase_letters(
    db: Connection, currency: str
) -> None:
    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Account), account_row(currency=currency))

    assert violated(exc) == "ck_accounts_currency_iso3"


def test_rejects_missing_required_value(db: Connection) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Deposit), deposit_row(account_id, currency=None))

    orig = exc.value.orig
    assert isinstance(orig, psycopg.errors.NotNullViolation)
    assert orig.diag.column_name == "currency"


# --- multi-column state rules ------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"status": "open", "settled_at": T1}, id="open-with-settled_at"),
        pytest.param({"status": "open", "payout_minor": 500}, id="open-with-payout"),
        pytest.param({"status": "won", "payout_minor": 500}, id="won-without-settled_at"),
        pytest.param({"status": "void"}, id="void-without-settled_at"),
    ],
)
def test_rejects_bet_settlement_that_contradicts_status(
    db: Connection, overrides: dict[str, Any]
) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Bet), bet_row(account_id, **overrides))

    assert violated(exc) == "ck_bets_settlement_matches_status"


def test_rejects_negative_payout(db: Connection) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Bet), bet_row(account_id, status="won", settled_at=T1, payout_minor=-1))

    assert violated(exc) == "ck_bets_payout_not_negative"


def test_rejects_closed_case_without_closed_at(db: Connection) -> None:
    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Case), case_row(status="closed"))

    assert violated(exc) == "ck_cases_closed_has_closed_at"


@pytest.mark.parametrize(
    "details",
    [
        pytest.param([1, 2], id="array"),
        pytest.param("text", id="string"),
        pytest.param(7, id="number"),
        # SQLAlchemy stores Python None in a JSONB column as JSON `null`, not SQL NULL,
        # so NOT NULL doesn't catch it; the CHECK must.
        pytest.param(None, id="json-null"),
    ],
)
def test_rejects_alert_details_that_are_not_a_json_object(db: Connection, details: Any) -> None:
    account_id = add_account(db)

    with pytest.raises(IntegrityError) as exc:
        db.execute(insert(Alert), alert_row(account_id, details=details))

    assert violated(exc) == "ck_alerts_details_is_object"


# --- approved in review: audit rows never cascade away ----------------------------------


def test_cannot_delete_account_that_has_deposits(db: Connection) -> None:
    account_id = add_account(db)
    db.execute(insert(Deposit), deposit_row(account_id))

    with pytest.raises(IntegrityError) as exc:
        db.execute(delete(Account).where(Account.id == account_id))

    assert violated(exc) == "fk_deposits_account_id_accounts"
