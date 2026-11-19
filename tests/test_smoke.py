"""First test: proves the package installs and imports correctly."""

import app


def test_package_imports_and_has_version() -> None:
    assert app.__version__ == "0.1.0"
