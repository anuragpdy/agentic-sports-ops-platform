"""Logging setup: one call at startup, then use logging.getLogger(__name__) everywhere."""

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
