"""Model metadata checks that need no database. DB behaviour is tested in tests/integration."""

from sqlalchemy import CheckConstraint, Table, create_engine
from sqlalchemy.schema import CreateTable

from app.db import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.base import Base

TABLES = Base.metadata.tables
# Only the dialect is used; create_engine does not connect until first use.
PG = create_engine("postgresql+psycopg://").dialect


def _checks(table: Table) -> dict[str, str]:
    return {
        str(c.name): str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
    }


def test_exactly_the_six_spec_tables() -> None:
    assert set(TABLES) == {"accounts", "deposits", "bets", "alerts", "cases", "alert_labels"}


def test_only_spec_optional_columns_are_nullable() -> None:
    nullable = {f"{t.name}.{c.name}" for t in TABLES.values() for c in t.columns if c.nullable}

    assert nullable == {
        "bets.settled_at",
        "bets.payout_minor",
        "alerts.case_id",
        "cases.closed_at",
        "cases.resolution",
    }


def test_every_foreign_key_column_is_indexed() -> None:
    for table in TABLES.values():
        # Columns that lead an index or the primary key can be looked up fast.
        leading = {next(iter(ix.columns)).name for ix in table.indexes}
        leading.add(next(iter(table.primary_key.columns)).name)
        for fk in table.foreign_keys:
            assert fk.parent.name in leading, f"{table.name}.{fk.parent.name} has no index"


def test_constraint_names_follow_the_convention() -> None:
    assert set(_checks(TABLES["bets"])) == {
        "ck_bets_stake_positive",
        "ck_bets_currency_iso3",
        "ck_bets_odds_gt_one",
        "ck_bets_status_allowed",
        "ck_bets_payout_not_negative",
        "ck_bets_settlement_matches_status",
    }
    fk_names = {fk.name for fk in TABLES["deposits"].foreign_key_constraints}
    assert fk_names == {"fk_deposits_account_id_accounts"}


def test_allowed_values_come_from_the_literal_types() -> None:
    assert _checks(TABLES["deposits"])["ck_deposits_method_allowed"] == (
        "method IN ('card', 'upi', 'bank', 'wallet')"
    )
    assert _checks(TABLES["accounts"])["ck_accounts_currency_iso3"] == "currency ~ '^[A-Z]{3}$'"


def test_postgres_types_for_money_odds_time_and_json() -> None:
    bets_sql = str(CreateTable(TABLES["bets"]).compile(dialect=PG))
    alerts_sql = str(CreateTable(TABLES["alerts"]).compile(dialect=PG))

    assert "stake_minor BIGINT NOT NULL" in bets_sql
    assert "odds NUMERIC(8, 3) NOT NULL" in bets_sql
    assert "placed_at TIMESTAMP WITH TIME ZONE NOT NULL" in bets_sql
    assert "id UUID NOT NULL" in bets_sql
    assert "details JSONB NOT NULL" in alerts_sql
