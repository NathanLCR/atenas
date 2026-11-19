"""Trusted client network allowlist for the local-only guard (Docker bridge)."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from core.skill_registry import SkillRegistry


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        output_dir=tmp_path / "output",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
        **overrides,
    )


async def _get(settings: Settings, peer: str, headers: dict[str, str] | None = None) -> int:
    transport = httpx.ASGITransport(
        app=create_app(settings=settings, registry=SkillRegistry()), client=(peer, 5000)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return (await client.get("/health", headers=headers)).status_code


@pytest.mark.asyncio
async def test_trusted_gateway_peer_is_allowed(tmp_path) -> None:
    settings = _settings(tmp_path, trusted_client_networks="172.30.57.1/32")
    assert await _get(settings, "172.30.57.1") == 200


@pytest.mark.asyncio
async def test_other_private_peer_is_still_rejected(tmp_path) -> None:
    settings = _settings(tmp_path, trusted_client_networks="172.30.57.1/32")
    assert await _get(settings, "172.30.57.2") == 403
    assert await _get(settings, "10.0.0.5") == 403


@pytest.mark.asyncio
async def test_default_rejects_docker_bridge_peer(tmp_path) -> None:
    assert await _get(_settings(tmp_path), "172.18.0.1") == 403


@pytest.mark.asyncio
async def test_trusted_peer_still_subject_to_forwarded_for_check(tmp_path) -> None:
    settings = _settings(tmp_path, trusted_client_networks="172.30.57.1/32")
    assert await _get(settings, "172.30.57.1", {"X-Forwarded-For": "203.0.113.9"}) == 403
    assert await _get(settings, "172.30.57.1", {"X-Forwarded-For": "172.30.57.1"}) == 200


@pytest.mark.parametrize(
    "value",
    ["0.0.0.0/0", "::/0", "8.8.8.0/24", "1.1.1.0/24", "not-a-cidr", "172.30.57.1/32,0.0.0.0/0"],
)
def test_invalid_or_public_networks_rejected_at_config(tmp_path, value: str) -> None:
    with pytest.raises(ValidationError):
        _settings(tmp_path, trusted_client_networks=value)


def test_networks_parsed_from_comma_separated_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TRUSTED_CLIENT_NETWORKS", "172.30.57.1/32, 10.0.0.0/8")
    settings = _settings(tmp_path)
    assert settings.trusted_client_networks == ["172.30.57.1/32", "10.0.0.0/8"]


def test_default_is_empty(tmp_path) -> None:
    assert _settings(tmp_path).trusted_client_networks == []
