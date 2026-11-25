"""The rules that keep integration tests off the dev database and honest in CI."""

import pytest

from tests.integration.db_guard import decide

TEST_URL = "postgresql://u:p@localhost:5432/sportsops_test"


@pytest.mark.parametrize("raw", [None, ""])
def test_unset_url_skips_locally(raw: str | None) -> None:
    decision = decide(raw, app_env="local")

    assert decision.action == "skip"
    assert "TEST_DATABASE_URL is not set" in decision.reason


@pytest.mark.parametrize("raw", [None, ""])
def test_unset_url_fails_in_ci(raw: str | None) -> None:
    decision = decide(raw, app_env="ci")

    assert decision.action == "fail"
    assert "required in CI" in decision.reason


@pytest.mark.parametrize("app_env", ["local", "ci"])
@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("postgresql://u:p@localhost:5432/sportsops", id="dev-db"),
        pytest.param("postgresql://u:p@localhost:5432/sportsops_test_copy", id="test-not-suffix"),
        pytest.param("postgresql://u:p@localhost:5432", id="no-db-name"),
    ],
)
def test_database_not_ending_in_test_is_refused(raw: str, app_env: str) -> None:
    decision = decide(raw, app_env=app_env)

    assert decision.action == "fail"
    assert "does not end with '_test'" in decision.reason


def test_test_database_runs_with_psycopg3_url() -> None:
    decision = decide(TEST_URL, app_env="ci")

    assert decision.action == "run"
    assert decision.url is not None
    assert decision.url.database == "sportsops_test"
    assert decision.url.drivername == "postgresql+psycopg"


def test_reason_never_contains_the_password() -> None:
    decision = decide("postgresql://u:hunter2@localhost:5432/sportsops", app_env="local")

    assert "hunter2" not in decision.reason
