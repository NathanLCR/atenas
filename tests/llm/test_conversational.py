"""Tests for the conversational service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.llm.client import OllamaClient, OllamaResponse
from core.llm.conversational import ConversationalService, FALLBACK_GREETING


def _mock_client(response_text: str) -> MagicMock:
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate.return_value = OllamaResponse(text=response_text, model="llama3.1:8b")
    return mock_client


def _mock_client_unavailable() -> MagicMock:
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate.side_effect = ConnectionError("Ollama unavailable")
    return mock_client


class TestConversationalService:
    def test_generates_response_from_llm(self) -> None:
        client = _mock_client("Hi there! How can I help you with your studies today?")
        service = ConversationalService(client)

        result = service.generate_response("hello")

        assert result == "Hi there! How can I help you with your studies today?"
        client.generate.assert_called_once()
        prompt = client.generate.call_args.args[0]
        assert "<user_message>" in prompt
        assert "hello" in prompt

    def test_fallback_when_ollama_unavailable(self) -> None:
        client = _mock_client_unavailable()
        service = ConversationalService(client)

        result = service.generate_response("hi")

        assert result == FALLBACK_GREETING
        assert "Atenas" in result
        assert "study assistant" in result

    def test_strips_whitespace_from_response(self) -> None:
        client = _mock_client("  Hello! I can help with your studies.  \n")
        service = ConversationalService(client)

        result = service.generate_response("hey")

        assert result == "Hello! I can help with your studies."

    def test_timeout_returns_fallback(self) -> None:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate.side_effect = TimeoutError("Request timed out")
        service = ConversationalService(mock_client)

        result = service.generate_response("good morning")

        assert result == FALLBACK_GREETING

    def test_os_error_returns_fallback(self) -> None:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate.side_effect = OSError("Network error")
        service = ConversationalService(mock_client)

        result = service.generate_response("how are you?")

        assert result == FALLBACK_GREETING
