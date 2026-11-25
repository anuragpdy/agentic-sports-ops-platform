"""create core tables

Revision ID: c318440307dc
Revises:
Create Date: 2026-11-25 09:30:17.152712

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c318440307dc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("country", sa.CHAR(length=2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name=op.f("ck_accounts_country_iso2")),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_accounts_currency_iso3")),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'closed')", name=op.f("ck_accounts_status_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status <> 'closed' OR closed_at IS NOT NULL",
            name=op.f("ck_cases_closed_has_closed_at"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'closed')", name=op.f("ck_cases_status_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cases")),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high')", name=op.f("ck_alerts_severity_allowed")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_alerts_account_id_accounts")
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name=op.f("fk_alerts_case_id_cases")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(op.f("ix_alerts_account_id"), "alerts", ["account_id"], unique=False)
    op.create_index(op.f("ix_alerts_case_id"), "alerts", ["case_id"], unique=False)
    op.create_table(
        "bets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("event_ref", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("selection", sa.Text(), nullable=False),
        sa.Column("stake_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("odds", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payout_minor", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "(status = 'open' AND settled_at IS NULL AND payout_minor IS NULL)"
            " OR (status <> 'open' AND settled_at IS NOT NULL)",
            name=op.f("ck_bets_settlement_matches_status"),
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_bets_currency_iso3")),
        sa.CheckConstraint(
            "status IN ('open', 'won', 'lost', 'void')", name=op.f("ck_bets_status_allowed")
        ),
        sa.CheckConstraint("odds > 1.000", name=op.f("ck_bets_odds_gt_one")),
        sa.CheckConstraint("payout_minor >= 0", name=op.f("ck_bets_payout_not_negative")),
        sa.CheckConstraint("stake_minor > 0", name=op.f("ck_bets_stake_positive")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_bets_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bets")),
    )
    op.create_index(
        "ix_bets_account_id_placed_at", "bets", ["account_id", "placed_at"], unique=False
    )
    op.create_table(
        "deposits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_deposits_currency_iso3")),
        sa.CheckConstraint(
            "method IN ('card', 'upi', 'bank', 'wallet')", name=op.f("ck_deposits_method_allowed")
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_deposits_amount_positive")),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_deposits_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deposits")),
    )
    op.create_index(op.f("ix_deposits_account_id"), "deposits", ["account_id"], unique=False)
    op.create_table(
        "alert_labels",
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "label IN ('fraud', 'benign')", name=op.f("ck_alert_labels_label_allowed")
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"], name=op.f("fk_alert_labels_alert_id_alerts")
        ),
        sa.PrimaryKeyConstraint("alert_id", name=op.f("pk_alert_labels")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("alert_labels")
    op.drop_index(op.f("ix_deposits_account_id"), table_name="deposits")
    op.drop_table("deposits")
    op.drop_index("ix_bets_account_id_placed_at", table_name="bets")
    op.drop_table("bets")
    op.drop_index(op.f("ix_alerts_case_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_account_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("cases")
    op.drop_table("accounts")
