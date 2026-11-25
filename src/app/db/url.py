"""Turn the app's DATABASE_URL into a URL SQLAlchemy can use.

Settings keep a plain `postgresql://...` URL, because psycopg (used by /ready) expects that
form. SQLAlchemy reads `postgresql://` as "use psycopg2", which we don't install, so we
switch the driver name to `postgresql+psycopg` (psycopg 3) here, in one place.
"""

from sqlalchemy.engine import URL, make_url


def sqlalchemy_url(database_url: str) -> URL:
    """Return a SQLAlchemy URL that uses the psycopg 3 driver.

    Returns a URL object, not a string: str(URL) masks the password, which is what you want
    in logs but would break a connection if passed back to create_engine.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"expected a postgresql:// URL, got backend {url.get_backend_name()!r}")
    return url.set(drivername="postgresql+psycopg")
