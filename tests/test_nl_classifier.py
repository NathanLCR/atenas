"""Tests for the natural language intent classifier."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from core.llm.client import OllamaClient, OllamaResponse
from core.nl.classifier import NLClassifier
from core.nl.intent import INTENT_ASK_NOTES, INTENT_TODAY, INTENT_ADD_ASSIGNMENT, INTENT_UNKNOWN, CONFIDENCE_THRESHOLD


def _make_classifier() -> NLClassifier:
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.1:8b", timeout=30)
    return NLClassifier(client, timezone="Europe/Dublin")


def _mock_generate(response_text: str):
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate.return_value = OllamaResponse(text=response_text, model="llama3.1:8b")
    mock_client.is_available.return_value = True
    return mock_client


class TestNLClassifier:
    def test_classifies_today_intent(self) -> None:
        response = json.dumps({
            "intent": "today",
            "confidence": 0.95,
            "slots": {},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("what's my plan for today?")

        assert result.intent == INTENT_TODAY
        assert result.confidence == 0.95
        assert result.is_confident is True
        assert result.is_read is True

    def test_classifies_add_assignment_intent(self) -> None:
        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.92,
            "slots": {"title": "ML exam", "due_at": "Friday at 5pm", "priority": "high"},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("add an assignment: ML exam due Friday at 5pm, priority high")

        assert result.intent == INTENT_ADD_ASSIGNMENT
        assert result.confidence == 0.92
        assert result.is_write is True
        assert result.slots["title"] == "ML exam"

    def test_classifies_ask_notes_intent(self) -> None:
        response = json.dumps({
            "intent": "ask_notes",
            "confidence": 0.93,
            "slots": {"query": "CNNs"},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("what do my notes say about CNNs?")

        assert result.intent == INTENT_ASK_NOTES
        assert result.slots["query"] == "CNNs"

    def test_low_confidence_falls_back_to_ask_notes(self) -> None:
        response = json.dumps({
            "intent": "today",
            "confidence": 0.4,
            "slots": {},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("hello")

        assert result.intent == INTENT_ASK_NOTES
        assert result.confidence == 0.4
        assert result.slots["query"] == "hello"

    def test_connection_error_falls_back_to_ask_notes(self) -> None:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate.side_effect = ConnectionError("Ollama unavailable")
        classifier = NLClassifier(mock_client, timezone="Europe/Dublin")
        result = classifier.classify("what's my schedule?")

        assert result.intent == INTENT_ASK_NOTES
        assert result.confidence == 0.0
        assert result.slots["query"] == "what's my schedule?"

    def test_generic_exception_returns_unknown(self) -> None:
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.generate.side_effect = RuntimeError("unexpected error")
        classifier = NLClassifier(mock_client, timezone="Europe/Dublin")
        result = classifier.classify("test")

        assert result.intent == INTENT_UNKNOWN
        assert result.confidence == 0.0

    def test_invalid_json_falls_back_to_ask_notes(self) -> None:
        classifier = NLClassifier(_mock_generate("not json at all"), timezone="Europe/Dublin")
        result = classifier.classify("some message")

        assert result.intent == INTENT_ASK_NOTES
        assert result.slots["query"] == "some message"

    def test_normalizes_priority_in_slots(self) -> None:
        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.9,
            "slots": {"title": "Test", "due_at": "2026-05-22", "priority": "high"},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("add assignment Test due 2026-05-22 priority high")

        assert result.slots["priority"] == "5"

    def test_normalizes_priority_numeric(self) -> None:
        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.9,
            "slots": {"title": "Test", "due_at": "2026-05-22", "priority": "3"},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("add assignment Test priority 3")

        assert result.slots["priority"] == "3"

    def test_handles_json_in_wrapping_text(self) -> None:
        wrapped = 'Here is the result:\n{"intent": "week", "confidence": 0.88, "slots": {}}\nHope that helps!'
        classifier = NLClassifier(_mock_generate(wrapped), timezone="Europe/Dublin")
        result = classifier.classify("show my weekly schedule")

        assert result.intent == "week"
        assert result.confidence == 0.88

    def test_empty_slots_dict(self) -> None:
        response = json.dumps({
            "intent": "today",
            "confidence": 0.9,
            "slots": {},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("today?")

        assert result.slots == {}

    def test_null_slots_values_filtered(self) -> None:
        response = json.dumps({
            "intent": "add_assignment",
            "confidence": 0.9,
            "slots": {"title": "Test", "module": None},
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("add assignment Test")

        assert "title" in result.slots
        assert "module" not in result.slots

    def test_non_dict_slots_treated_as_empty(self) -> None:
        response = json.dumps({
            "intent": "today",
            "confidence": 0.9,
            "slots": ["not", "a", "dict"],
        })
        classifier = NLClassifier(_mock_generate(response), timezone="Europe/Dublin")
        result = classifier.classify("today")

        assert result.slots == {}
