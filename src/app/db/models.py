"""SQLAlchemy models for the six M2 tables (see docs/specs/m02-data-model.md).

Rules the database enforces itself (so bad rows fail even if some future code skips
validation): NOT NULL, foreign keys, positive amounts, odds > 1, allowed values via
TEXT + CHECK (not Postgres ENUM types, which are awkward to change in a migration), and
state rules that span columns (an open bet has no settlement; a closed case has closed_at).

Conventions: money = BIGINT minor units + a 3-letter currency, never float. Odds =
NUMERIC(8,3) <-> Decimal. IDs = UUID v4 made in Python. Timestamps = timestamptz.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, get_args

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.schemas.values import (
    AccountStatus,
    AlertSeverity,
    BetStatus,
    CaseStatus,
    DepositMethod,
    FraudLabel,
)

# timestamptz: Postgres stores an absolute instant (UTC internally), never a wall-clock time.
TIMESTAMPTZ = DateTime(timezone=True)


def _one_of(column: str, allowed: Any) -> str:
    """SQL for a CHECK that `column` is one of the values of a Literal type."""
    values = ", ".join(f"'{v}'" for v in get_args(allowed))
    return f"{column} IN ({values})"


def _code(column: str, length: int) -> str:
    """SQL for a CHECK that `column` is exactly `length` uppercase letters (ISO codes).

    CHAR(n) alone would accept 'in' or a padded 'IN ' for a 3-letter currency.
    """
    return f"{column} ~ '^[A-Z]{{{length}}}$'"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(_code("country", 2), name="country_iso2"),
        CheckConstraint(_code("currency", 3), name="currency_iso3"),
        CheckConstraint(_one_of("status", AccountStatus), name="status_allowed"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    country: Mapped[str] = mapped_column(CHAR(2))
    currency: Mapped[str] = mapped_column(CHAR(3))
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)


class Deposit(Base):
    __tablename__ = "deposits"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        CheckConstraint(_code("currency", 3), name="currency_iso3"),
        CheckConstraint(_one_of("method", DepositMethod), name="method_allowed"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3))
    method: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (
        CheckConstraint("stake_minor > 0", name="stake_positive"),
        CheckConstraint(_code("currency", 3), name="currency_iso3"),
        CheckConstraint("odds > 1.000", name="odds_gt_one"),
        CheckConstraint(_one_of("status", BetStatus), name="status_allowed"),
        CheckConstraint("payout_minor >= 0", name="payout_not_negative"),
        # Open bet: nothing settled yet. Won/lost/void: settled_at must be set.
        CheckConstraint(
            "(status = 'open' AND settled_at IS NULL AND payout_minor IS NULL)"
            " OR (status <> 'open' AND settled_at IS NOT NULL)",
            name="settlement_matches_status",
        ),
        # "Recent bets of an account". Its leading column also serves lookups by
        # account_id alone, so account_id gets no separate index.
        Index("ix_bets_account_id_placed_at", "account_id", "placed_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    event_ref: Mapped[str] = mapped_column(Text)
    market: Mapped[str] = mapped_column(Text)
    selection: Mapped[str] = mapped_column(Text)
    stake_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(CHAR(3))
    odds: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    status: Mapped[str] = mapped_column(Text)
    placed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    settled_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    payout_minor: Mapped[int | None] = mapped_column(BigInteger)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(_one_of("status", CaseStatus), name="status_allowed"),
        CheckConstraint("status <> 'closed' OR closed_at IS NOT NULL", name="closed_has_closed_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    status: Mapped[str] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    resolution: Mapped[str | None] = mapped_column(Text)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (CheckConstraint(_one_of("severity", AlertSeverity), name="severity_allowed"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cases.id"), index=True)
    rule: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)


class AlertLabel(Base):
    """Ground truth for evals. Kept apart from alerts so agent tools can be denied it (M4)."""

    __tablename__ = "alert_labels"
    __table_args__ = (CheckConstraint(_one_of("label", FraudLabel), name="label_allowed"),)

    # PK = FK: at most one label per alert; the PK index covers lookups by alert_id.
    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
