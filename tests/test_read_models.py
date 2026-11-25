"""Read-model guarantees that need no database: strict types, aware times, frozen."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.entities import BetRead, CaseRead
from tests.rows import bet_row, case_row


def _bet(**overrides: Any) -> dict[str, Any]:
    return bet_row(uuid.uuid4(), **overrides)


def test_valid_bet_builds() -> None:
    assert BetRead.model_validate(_bet()).odds == Decimal("2.150")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("odds", 2.15, id="float-odds"),
        pytest.param("stake_minor", 100.0, id="float-stake"),
        pytest.param("stake_minor", Decimal("100"), id="decimal-stake"),
        pytest.param("stake_minor", "100", id="string-stake"),
        pytest.param("id", "1b4e28ba-2fa1-11d2-883f-0016d3cca427", id="string-uuid"),
    ],
)
def test_strict_mode_refuses_to_convert_types(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        BetRead.model_validate(_bet(**{field: value}))


def test_timestamp_without_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        BetRead.model_validate(_bet(placed_at=datetime(2026, 1, 1, 12, 0)))


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CaseRead.model_validate(case_row(status="archived"))


def test_read_models_are_frozen() -> None:
    bet = BetRead.model_validate(_bet())

    with pytest.raises(ValidationError, match="frozen"):
        bet.stake_minor = 1  # type: ignore[misc]
