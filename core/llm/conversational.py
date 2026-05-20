"""Conversational service for generating LLM-based responses to greetings and small talk."""

from __future__ import annotations

import logging

from core.llm.client import OllamaClient
from core.llm.conversational_prompts import CONVERSATIONAL_PROMPT

logger = logging.getLogger(__name__)

FALLBACK_GREETING = "Hi! I'm Atenas, your study assistant. How can I help you today? You can ask about your schedule, assignments, notes, or use /help to see all commands."


class ConversationalService:
    """Generate conversational responses using local LLM.

    Handles greetings, small talk, and general chat while maintaining
    the assistant's identity as a study assistant.
    """

    def __init__(self, ollama_client: OllamaClient) -> None:
        self._client = ollama_client

    def generate_response(self, message: str) -> str:
        """Generate a conversational response to the user message.

        Returns an LLM-generated response, or a fallback greeting if
        Ollama is unavailable.
        """
        try:
            prompt = CONVERSATIONAL_PROMPT.format(user_message=message)
            response = self._client.generate(prompt)
            return response.text.strip()
        except (ConnectionError, TimeoutError, OSError):
            logger.warning("ollama_unavailable_conversational_response")
            return FALLBACK_GREETING
