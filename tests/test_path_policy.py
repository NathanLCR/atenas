from pathlib import Path

import pytest

from core.path_policy import PathPolicy, PathPolicyError


def test_allows_file_inside_allowed_root(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    allowed = inbox / "reading.txt"
    allowed.write_text("safe text", encoding="utf-8")

    policy = PathPolicy([inbox])

    assert policy.validate_registered_file(allowed) == allowed.resolve()


def test_rejects_env_file_even_inside_allowed_root(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    env_file = inbox / ".env"
    env_file.write_text("TOKEN=secret", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="hidden or secret"):
        policy.validate_registered_file(env_file)


def test_rejects_parent_directory_escape(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not allowed", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="allowed roots"):
        policy.validate_registered_file(inbox / ".." / "outside.txt")


def test_rejects_symlink_escape(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not allowed", encoding="utf-8")
    link = inbox / "linked.txt"
    link.symlink_to(outside)

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="allowed roots"):
        policy.validate_registered_file(link)


def test_rejects_source_files_by_suffix(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "app.py"
    source.write_text("print('no')", encoding="utf-8")

    policy = PathPolicy([inbox])

    with pytest.raises(PathPolicyError, match="source code"):
        policy.validate_registered_file(source)
