"""Alembic environment: how `alembic upgrade/downgrade/revision` connect and what they compare.

Where the database URL comes from, in order:
1. A connection passed in by code (`config.attributes["connection"]`) — the tests use this
   to point Alembic at sportsops_test without touching settings.
2. Otherwise DATABASE_URL from app Settings (.env or environment), the same value the app uses.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db.url import sqlalchemy_url

# Models must be imported so their tables register on Base.metadata (added in slice 2):
# from app.db import models  # noqa: F401

config = context.config

# Use alembic.ini's logging setup for CLI runs only; when tests call Alembic from code,
# leave pytest's logging alone.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


# Also diff column types and server defaults, so the "models match migrations" test
# catches more than added/removed tables and columns.
COMPARE_TYPE = True
COMPARE_SERVER_DEFAULT = True


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it (handy for review)."""
    context.configure(
        url=sqlalchemy_url(get_settings().database_url.get_secret_value()),
        target_metadata=target_metadata,
        compare_type=COMPARE_TYPE,
        compare_server_default=COMPARE_SERVER_DEFAULT,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=COMPARE_TYPE,
        compare_server_default=COMPARE_SERVER_DEFAULT,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    given = config.attributes.get("connection")
    if given is not None:
        _run_with(given)
        return
    # NullPool: a migration is a one-off command, so don't keep pooled connections open.
    engine = create_engine(
        sqlalchemy_url(get_settings().database_url.get_secret_value()),
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        _run_with(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
