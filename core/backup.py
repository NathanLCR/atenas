"""Local zip backup and restore for Atenas runtime state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Protocol


class BackupSettings(Protocol):
    """Settings surface required by the backup service."""

    @property
    def db_path(self) -> Path: ...

    @property
    def data_dir(self) -> Path: ...

    @property
    def memory_dir(self) -> Path: ...

    @property
    def output_dir(self) -> Path: ...

    @property
    def inbox_dir(self) -> Path: ...

    @property
    def logs_dir(self) -> Path: ...


class BackupService:
    """Create and restore explicit local Atenas backup archives."""

    def __init__(
        self,
        settings: BackupSettings,
        *,
        project_root: Path | str | None = None,
    ) -> None:
        self.settings = settings
        self.project_root = Path(project_root) if project_root is not None else Path.cwd()

    def create_backup(self, *, include_logs: bool = False) -> Path:
        """Create a timestamped backup archive and return its path."""

        backup_dir = Path(self.settings.output_dir) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        created_at = _utc_timestamp()
        archive_path = backup_dir / f"atenas-backup-{created_at.replace(':', '').replace('-', '')}.zip"

        files = self._included_files(include_logs=include_logs)
        manifest = {
            "version": 1,
            "created_at": created_at,
            "db_path": str(self.settings.db_path),
            "include_logs": include_logs,
            "included_files": [item for item in files],
            "excluded_secret_paths": [".env"],
        }

        db_path = Path(self.settings.db_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "atenas_snapshot.sqlite"
            if db_path.exists():
                src = sqlite3.connect(str(db_path))
                try:
                    dst = sqlite3.connect(str(snapshot_path))
                    try:
                        src.backup(dst)
                    finally:
                        dst.close()
                finally:
                    src.close()

            with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in files:
                    source = item["source_path"]
                    arc = item["archive_path"]
                    if arc == "data/atenas.sqlite" and snapshot_path.exists():
                        archive.write(str(snapshot_path), arc)
                    else:
                        archive.write(source, arc)
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2, sort_keys=True),
                )
        return archive_path

    def restore_backup(self, archive_path: Path, *, force: bool = False) -> None:
        """Restore a backup archive into this service's configured paths."""

        with zipfile.ZipFile(archive_path) as archive:
            manifest = self._read_manifest(archive)
            included_files = manifest["included_files"]
            db_item = _find_db_item(included_files)
            db_destination = self._destination_for_archive_path(db_item["archive_path"])
            if db_destination.exists() and not force:
                raise FileExistsError(f"Database already exists: {db_destination}")

            for item in included_files:
                member = item["archive_path"]
                destination = self._destination_for_archive_path(member)
                if destination.exists() and not force:
                    raise FileExistsError(f"Backup target already exists: {destination}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source:
                    destination.write_bytes(source.read())

    def _included_files(self, *, include_logs: bool) -> list[dict[str, object]]:
        files: list[dict[str, object]] = []
        files.extend(_file_entry(path, "data/atenas.sqlite") for path in [self.settings.db_path] if path.exists())
        files.extend(
            _file_entry(path, _archive_path_for(self.settings.memory_dir, "memory", path))
            for path in _iter_files(self.settings.memory_dir)
        )
        files.extend(
            _file_entry(path, _archive_path_for(self.settings.inbox_dir, "inbox", path))
            for path in _iter_files(self.settings.inbox_dir)
        )
        if include_logs:
            files.extend(
                _file_entry(path, _archive_path_for(self.settings.logs_dir, "logs", path))
                for path in _iter_files(self.settings.logs_dir)
            )
        return files

    def _read_manifest(self, archive: zipfile.ZipFile) -> dict:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except KeyError as exc:
            raise ValueError("Backup archive is missing manifest.json") from exc
        if manifest.get("version") != 1:
            raise ValueError("Unsupported backup manifest version")
        included_files = manifest.get("included_files")
        if not isinstance(included_files, list):
            raise ValueError("Backup manifest is missing included_files")
        return manifest

    def _destination_for_archive_path(self, archive_path: str) -> Path:
        parts = _safe_archive_parts(archive_path)
        if parts == ("data", "atenas.sqlite"):
            return Path(self.settings.db_path)
        if parts and parts[0] == "memory":
            return Path(self.settings.memory_dir).joinpath(*parts[1:])
        if parts and parts[0] == "inbox":
            return Path(self.settings.inbox_dir).joinpath(*parts[1:])
        if parts and parts[0] == "logs":
            return Path(self.settings.logs_dir).joinpath(*parts[1:])
        raise ValueError(f"Unsupported backup member: {archive_path}")


def _iter_files(directory: Path) -> list[Path]:
    path = Path(directory)
    if not path.exists():
        return []
    return sorted(item for item in path.rglob("*") if item.is_file())


def _archive_path_for(root: Path, label: str, path: Path) -> str:
    return PurePosixPath(label).joinpath(path.relative_to(root).as_posix()).as_posix()


def _file_entry(path: Path, archive_path: str) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "source_path": str(path),
        "archive_path": archive_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def _find_db_item(included_files: list[dict]) -> dict:
    for item in included_files:
        if item.get("archive_path") == "data/atenas.sqlite":
            return item
    raise ValueError("Backup archive does not contain data/atenas.sqlite")


def _safe_archive_parts(archive_path: str) -> tuple[str, ...]:
    pure = PurePosixPath(archive_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"Unsafe backup member path: {archive_path}")
    return tuple(pure.parts)


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
