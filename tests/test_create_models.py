"""Create-model guarantees (M3 D4, D5; closes I5 and I6). No database needed."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.create import (
    AccountCreate,
    AlertCreate,
    AlertLabelCreate,
    BetCreate,
    DepositCreate,
)
from tests.rows import (
    T0,
    account_row,
    alert_label_row,
    alert_row,
    bet_row,
    deposit_row,
)

ACCOUNT_ID = uuid.uuid4()
IST = timezone(timedelta(hours=5, minutes=30))

# (model, valid row, its timestamp fields). Every timestamp of every model is probed.
CASES: list[tuple[type[BaseModel], dict[str, Any], list[str]]] = [
    (AccountCreate, account_row(), ["created_at"]),
    (DepositCreate, deposit_row(ACCOUNT_ID), ["created_at"]),
    (
        BetCreate,
        bet_row(ACCOUNT_ID, status="won", settled_at=T0, payout_minor=21500),
        ["placed_at", "settled_at"],
    ),
    (AlertCreate, alert_row(ACCOUNT_ID), ["created_at"]),
    (AlertLabelCreate, alert_label_row(uuid.uuid4()), ["created_at"]),
]
TIME_FIELDS = [
    pytest.param(model, row, field, id=f"{model.__name__}.{field}")
    for model, row, fields in CASES
    for field in fields
]


def _bet(**overrides: Any) -> dict[str, Any]:
    return bet_row(ACCOUNT_ID, **overrides)


@pytest.mark.parametrize(("model", "row"), [pytest.param(m, r, id=m.__name__) for m, r, _ in CASES])
def test_valid_row_builds(model: type[BaseModel], row: dict[str, Any]) -> None:
    model.model_validate(row)


# --- D4 / I5: odds are rejected, never rounded -------------------------------------------


@pytest.mark.parametrize("odds", ["2.150", "2.1500", "2.15", "1.001", "99999.999"])
def test_odds_that_fit_numeric_8_3_exactly_are_kept_unchanged(odds: str) -> None:
    bet = BetCreate.model_validate(_bet(odds=Decimal(odds)))

    assert bet.odds == Decimal(odds)


@pytest.mark.parametrize(
    ("odds", "message"),
    [
        pytest.param("2.1505", "no more than 3 decimal places", id="4dp-would-round"),
        pytest.param("2.0001", "no more than 3 decimal places", id="tiny-4th-place"),
        pytest.param("100000", "no more than 5 digits before the decimal", id="too-large"),
        pytest.param("NaN", "finite number", id="nan"),
        pytest.param("Infinity", "finite number", id="infinity"),
    ],
)
def test_odds_that_postgres_would_change_or_refuse_are_rejected(odds: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message) as exc:
        BetCreate.model_validate(_bet(odds=Decimal(odds)))

    assert exc.value.errors()[0]["loc"] == ("odds",)


def test_float_odds_are_rejected() -> None:
    # A float like 2.15 is really 2.14999…; strict mode refuses it rather than guessing.
    with pytest.raises(ValidationError):
        BetCreate.model_validate(_bet(odds=2.15))


# --- I7 (one-row rule the DB doesn't enforce): a lost bet pays 0 --------------------------


def test_lost_bet_with_zero_payout_builds() -> None:
    BetCreate.model_validate(_bet(status="lost", settled_at=T0, payout_minor=0))


@pytest.mark.parametrize(
    "payout", [pytest.param(500, id="positive"), pytest.param(None, id="null")]
)
def test_lost_bet_with_nonzero_payout_is_rejected(payout: int | None) -> None:
    with pytest.raises(ValidationError, match="a lost bet must have payout_minor 0"):
        BetCreate.model_validate(_bet(status="lost", settled_at=T0, payout_minor=payout))


# --- D5 / I6: timestamps must be aware and UTC -------------------------------------------


@pytest.mark.parametrize(("model", "row", "field"), TIME_FIELDS)
def test_naive_datetime_is_rejected(
    model: type[BaseModel], row: dict[str, Any], field: str
) -> None:
    with pytest.raises(ValidationError, match="timezone") as exc:
        model.model_validate(row | {field: datetime(2026, 1, 1, 12, 0)})

    assert exc.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(("model", "row", "field"), TIME_FIELDS)
def test_non_utc_datetime_is_rejected(
    model: type[BaseModel], row: dict[str, Any], field: str
) -> None:
    # Same instant as T0, but expressed in IST: still refused (all times are UTC by convention).
    with pytest.raises(ValidationError, match=r"must be in UTC") as exc:
        model.model_validate(row | {field: T0.astimezone(IST)})

    assert exc.value.errors()[0]["loc"] == (field,)


def test_utc_written_as_a_fixed_zero_offset_is_accepted() -> None:
    zero_offset = timezone(timedelta(0))

    bet = BetCreate.model_validate(_bet(placed_at=T0.replace(tzinfo=zero_offset)))

    assert bet.placed_at == T0


# --- config: strict, no stray fields, frozen ---------------------------------------------


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BetCreate.model_validate(_bet(label="fraud"))


def test_id_is_required() -> None:
    row = _bet()
    del row["id"]

    with pytest.raises(ValidationError, match="Field required"):
        BetCreate.model_validate(row)


def test_create_models_are_frozen() -> None:
    bet = BetCreate.model_validate(_bet())

    with pytest.raises(ValidationError, match="frozen"):
        bet.odds = Decimal("3.000")  # type: ignore[misc]
