"""Ollama-compatible HTTP client for local LLM calls."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OllamaResponse:
    text: str
    model: str
    done: bool = True


class OllamaClient:
    """Minimal HTTP client for Ollama's /api/generate endpoint.

    Uses only Python standard library (urllib). No external dependencies.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> OllamaResponse:
        """Send a generate request to Ollama and return the response text."""

        url = f"{self.base_url}/api/generate"
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return OllamaResponse(
                    text=data.get("response", ""),
                    model=data.get("model", self.model),
                    done=data.get("done", True),
                )
        except urllib.error.URLError as exc:
            raise ConnectionError(f"Ollama unavailable at {self.base_url}: {exc}") from exc
        except TimeoutError as exc:
            raise TimeoutError(f"Ollama request timed out after {self.timeout}s") from exc

    def is_available(self) -> bool:
        """Check if Ollama is reachable."""

        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False
