"""Declarative base shared by every SQLAlchemy model.

The naming convention gives every index and constraint a predictable name (e.g.
`ck_bets_odds_gt_one`, `fk_deposits_account_id_accounts`). Without it Postgres invents
names, and Alembic can't reliably drop or alter those constraints in a later migration
or downgrade, because the name may differ between machines.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # CHECK constraints must be given a name in the model; this prefixes it with the table.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
