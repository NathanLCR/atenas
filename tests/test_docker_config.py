"""Static checks for the Docker quickstart (no Docker daemon required)."""

from __future__ import annotations

import ipaddress
from pathlib import Path

import yaml

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_ports_publish_on_loopback_only() -> None:
    for port in _compose()["services"]["atenas"]["ports"]:
        assert str(port).startswith("127.0.0.1:")


def test_trusted_network_is_gateway_of_fixed_subnet() -> None:
    compose = _compose()
    env = compose["services"]["atenas"]["environment"]
    trusted = Settings(_env_file=None, trusted_client_networks=env["TRUSTED_CLIENT_NETWORKS"])
    ipam = compose["networks"]["atenas"]["ipam"]["config"][0]
    subnet = ipaddress.ip_network(ipam["subnet"])
    assert [str(n) for n in trusted.trusted_networks] == [f"{ipam['gateway']}/32"]
    assert all(n.subnet_of(subnet) for n in trusted.trusted_networks)


def test_ollama_reachable_from_container_and_optional_service_is_profiled() -> None:
    compose = _compose()
    service = compose["services"]["atenas"]
    assert "host.docker.internal:host-gateway" in service["extra_hosts"]
    assert "host.docker.internal" in service["environment"]["OLLAMA_BASE_URL"]
    assert service["environment"]["ALLOW_EXTERNAL_OLLAMA"] == "true"
    assert compose["services"]["ollama"]["profiles"] == ["ollama"]
    assert "ollama-models" in compose["volumes"]


def test_dockerfile_installs_package_healthchecks_and_stays_non_root() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --no-cache-dir --no-deps ." in text
    assert "HEALTHCHECK" in text and "/health" in text
    assert "curl" not in text
    assert "USER appuser" in text


def test_dockerignore_excludes_secrets_and_state() -> None:
    entries = set((ROOT / ".dockerignore").read_text(encoding="utf-8").split())
    assert {".env", ".env.*", "data/", "logs/", ".venv/", ".git/", ".pytest_cache/"} <= entries
