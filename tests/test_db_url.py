import pytest

from app.db.url import sqlalchemy_url


def test_switches_driver_to_psycopg3_and_keeps_the_rest() -> None:
    url = sqlalchemy_url("postgresql://user:secret1@localhost:5432/sportsops")

    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.password, url.host, url.port, url.database) == (
        "user",
        "secret1",
        "localhost",
        5432,
        "sportsops",
    )


def test_password_is_masked_when_printed() -> None:
    url = sqlalchemy_url("postgresql://user:secret1@localhost:5432/sportsops")

    assert "secret1" not in str(url)


def test_already_psycopg_url_is_unchanged() -> None:
    url = sqlalchemy_url("postgresql+psycopg://user:pw@localhost/db")

    assert url.drivername == "postgresql+psycopg"


def test_rejects_non_postgres_url() -> None:
    with pytest.raises(ValueError, match="postgresql"):
        sqlalchemy_url("sqlite:///local.db")
