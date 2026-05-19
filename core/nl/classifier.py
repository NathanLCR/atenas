"""Natural language intent classifier using local Ollama."""

from __future__ import annotations

import json
import logging
from zoneinfo import ZoneInfo

from core.llm.client import OllamaClient
from core.nl.intent import CONFIDENCE_THRESHOLD, INTENT_ASK_NOTES, INTENT_UNKNOWN, IntentMatch
from core.nl.prompts import CLASSIFICATION_PROMPT, INTENT_LIST
from core.nl.slots import extract_slots

logger = logging.getLogger(__name__)


class NLClassifier:
    """Classifies natural language messages into intents via Ollama."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        timezone: str = "Europe/Dublin",
    ) -> None:
        self._client = ollama_client
        self._tz = ZoneInfo(timezone)

    def classify(self, message: str) -> IntentMatch:
        """Classify a user message into an intent with slots.

        Returns an IntentMatch. If Ollama is unavailable, returns a
        fallback IntentMatch that routes to ask_notes.
        """
        try:
            prompt = CLASSIFICATION_PROMPT.format(
                intent_list=", ".join(INTENT_LIST),
                user_message=message,
            )
            response = self._client.generate(prompt)
            return self._parse_response(response.text, message)
        except ConnectionError:
            logger.warning("ollama_unavailable_nl_classification")
            return IntentMatch(
                intent=INTENT_ASK_NOTES,
                confidence=0.0,
                slots={"query": message},
            )
        except Exception:
            logger.exception("nl_classification_error")
            return IntentMatch(
                intent=INTENT_UNKNOWN,
                confidence=0.0,
                slots={},
            )

    def _parse_response(self, text: str, original_message: str) -> IntentMatch:
        cleaned = text.strip()
        json_start = cleaned.find("{")
        json_end = cleaned.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            cleaned = cleaned[json_start:json_end]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("nl_classifier_invalid_json", extra={"text": text[:200]})
            return IntentMatch(
                intent=INTENT_ASK_NOTES,
                confidence=0.0,
                slots={"query": original_message},
            )

        intent = data.get("intent", INTENT_UNKNOWN)
        confidence = float(data.get("confidence", 0.0))
        raw_slots = data.get("slots", {})

        if not isinstance(raw_slots, dict):
            raw_slots = {}

        slots = {k: str(v) for k, v in raw_slots.items() if v is not None}
        normalized_slots = extract_slots(slots, self._tz)

        if confidence < CONFIDENCE_THRESHOLD and intent != INTENT_ASK_NOTES:
            return IntentMatch(
                intent=INTENT_ASK_NOTES,
                confidence=confidence,
                slots={"query": original_message},
            )

        return IntentMatch(
            intent=intent,
            confidence=confidence,
            slots=normalized_slots,
        )
