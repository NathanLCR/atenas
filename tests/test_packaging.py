"""Packaging configuration tests."""

from __future__ import annotations

import tomllib
from pathlib import Path


def _pinned_requirement(name: str) -> str:
    prefix = f"{name}=="
    for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{name} is not pinned in requirements.txt")


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_editable_install_uses_explicit_package_discovery() -> None:
    """Editable installs should not auto-discover runtime data directories."""

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    find_config = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert set(find_config["include"]) == {"app*", "core*", "skills*"}
    assert set(find_config["exclude"]) >= {"data*", "logs*", "memory*", "output*", "inbox*", "web*"}


def test_requirements_pin_python314_compatible_pydantic_stack() -> None:
    """Pinned dev installs should not fall back to building old pydantic-core."""

    assert _version_tuple(_pinned_requirement("pydantic")) >= (2, 13, 4)
    assert _version_tuple(_pinned_requirement("pydantic-settings")) >= (2, 14, 0)


def test_requirements_includes_all_pyproject_dependencies() -> None:
    """Every [project] dependency name in pyproject.toml must appear in requirements.txt."""

    import re

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    req_text = Path("requirements.txt").read_text(encoding="utf-8").lower()

    for dep_spec in pyproject["project"]["dependencies"]:
        # Extract bare package name (before version specifier and extras).
        name = re.split(r"[>=<!;\[\s]", dep_spec, maxsplit=1)[0].strip().lower()
        # Normalise dashes/underscores for lookup.
        normalised = name.replace("-", "-").replace("_", "-")
        assert normalised in req_text, (
            f"'{name}' declared in pyproject.toml [project] dependencies "
            f"but not found in requirements.txt"
        )
