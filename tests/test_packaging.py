"""Packaging configuration tests."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_editable_install_uses_explicit_package_discovery() -> None:
    """Editable installs should not auto-discover runtime data directories."""

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    find_config = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert set(find_config["include"]) == {"app*", "core*", "skills*"}
    assert set(find_config["exclude"]) >= {"data*", "logs*", "memory*", "output*", "inbox*", "web*"}
