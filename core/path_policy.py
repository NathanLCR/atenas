"""Filesystem access policy for user-registered Atenas files."""

from __future__ import annotations

from pathlib import Path

SECRET_NAMES = {".env", ".env.local", ".netrc", "id_rsa", "id_ed25519"}
SECRET_PARTS = {".ssh", ".gnupg", ".aws", ".config"}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".sh", ".zsh"}


class PathPolicyError(ValueError):
    """Raised when a path violates Atenas file access policy."""


class PathPolicy:
    """Allow registered files only inside configured, non-secret data roots."""

    def __init__(self, allowed_roots: list[Path | str]) -> None:
        roots = [Path(root).expanduser().resolve() for root in allowed_roots]
        self.allowed_roots = [root for root in roots if root.exists()]
        if not self.allowed_roots:
            raise PathPolicyError("At least one existing allowed file root is required.")

    def validate_registered_file(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise PathPolicyError("File not found.") from exc

        if not resolved.is_file():
            raise PathPolicyError("Registered path must be a file.")
        if not self._inside_allowed_root(resolved):
            raise PathPolicyError("File must be inside one of the configured allowed roots.")
        if self._is_hidden_or_secret(resolved):
            raise PathPolicyError("Refusing hidden or secret file path.")
        if resolved.suffix.lower() in SOURCE_SUFFIXES:
            raise PathPolicyError("Refusing source code file path.")
        return resolved

    def _inside_allowed_root(self, path: Path) -> bool:
        return any(path == root or root in path.parents for root in self.allowed_roots)

    def _is_hidden_or_secret(self, path: Path) -> bool:
        parts = set(path.parts)
        if path.name in SECRET_NAMES:
            return True
        if parts & SECRET_PARTS:
            return True
        relative_parts = path.relative_to(self._matching_root(path)).parts
        return any(part.startswith(".") for part in relative_parts)

    def _matching_root(self, path: Path) -> Path:
        for root in self.allowed_roots:
            if path == root or root in path.parents:
                return root
        return self.allowed_roots[0]
