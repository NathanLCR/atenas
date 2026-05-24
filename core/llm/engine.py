"""Engine abstraction layer for local LLM providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.llm.client import OllamaClient, OllamaResponse

logger = logging.getLogger(__name__)


@dataclass
class EngineHealth:
    available: bool
    provider: str = "ollama"
    model: str | None = None
    models: list[str] = field(default_factory=list)
    error: str | None = None


class OllamaEngine:
    """Wraps OllamaClient behind a stable engine interface."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 60,
    ) -> None:
        self._client = OllamaClient(base_url=base_url, model=model, timeout=timeout)
        self.model = model

    def generate(self, prompt: str) -> OllamaResponse:
        return self._client.generate(prompt)

    def health(self) -> EngineHealth:
        try:
            models = self._client.list_models()
            return EngineHealth(
                available=True,
                provider="ollama",
                model=self.model,
                models=models,
            )
        except Exception as exc:
            return EngineHealth(
                available=False,
                provider="ollama",
                model=self.model,
                error=str(exc),
            )

    def list_models(self) -> list[str]:
        return self._client.list_models()
