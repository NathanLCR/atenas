"""Tests for the Ollama client."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from core.llm.client import OllamaClient, OllamaModelUnavailable, OllamaResponse


class TestOllamaClient:
    def test_builds_request_correctly(self) -> None:
        client = OllamaClient(base_url="http://localhost:11434", model="llama3.1:8b", timeout=30)
        assert client.base_url == "http://localhost:11434"
        assert client.model == "llama3.1:8b"
        assert client.timeout == 30

    def test_handles_success_response(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "model": "llama3.1:8b",
            "response": "Test output",
            "done": True,
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.generate("Test prompt")

        assert result.text == "Test output"
        assert result.model == "llama3.1:8b"
        assert result.done is True

    def test_handles_connection_failure(self) -> None:
        client = OllamaClient()

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            with pytest.raises(ConnectionError, match="Ollama unavailable"):
                client.generate("Test prompt")

    def test_handles_missing_model_response(self) -> None:
        client = OllamaClient(model="batiai/gemma4-e4b:q4")
        error = urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=404,
            msg="not found",
            hdrs=None,
            fp=MagicMock(),
        )
        error.fp.read.return_value = json.dumps(
            {"error": "model 'batiai/gemma4-e4b:q4' not found"}
        ).encode("utf-8")

        with patch("urllib.request.urlopen", side_effect=error):
            with pytest.raises(OllamaModelUnavailable, match="ollama pull batiai/gemma4-e4b:q4"):
                client.generate("Test prompt")

    def test_handles_timeout_error(self) -> None:
        client = OllamaClient(timeout=1)

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with pytest.raises(TimeoutError, match="timed out"):
                client.generate("Test prompt")

    def test_handles_malformed_response(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(json.JSONDecodeError):
                client.generate("Test prompt")

    def test_is_available_returns_true(self) -> None:
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            assert client.is_available() is True

    def test_is_available_returns_false_on_error(self) -> None:
        client = OllamaClient()

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.is_available() is False

    def test_strips_trailing_slash_from_base_url(self) -> None:
        client = OllamaClient(base_url="http://localhost:11434/")
        assert client.base_url == "http://localhost:11434"
