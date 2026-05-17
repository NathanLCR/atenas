"""Tests for LLM prompts."""

from __future__ import annotations

import pytest

from core.llm.prompts import (
    build_prompt,
    explain_prompt,
    flashcards_prompt,
    questions_prompt,
    rewrite_prompt,
    summarize_prompt,
)

NOTE_BODY = "Backpropagation computes gradients using the chain rule."


class TestPrompts:
    def test_summarize_prompt_includes_note(self) -> None:
        prompt = summarize_prompt(NOTE_BODY)
        assert NOTE_BODY in prompt
        assert "5 bullet points" in prompt

    def test_explain_prompt_includes_note(self) -> None:
        prompt = explain_prompt(NOTE_BODY)
        assert NOTE_BODY in prompt
        assert "MSc AI" in prompt

    def test_questions_prompt_includes_note(self) -> None:
        prompt = questions_prompt(NOTE_BODY)
        assert NOTE_BODY in prompt
        assert "short-answer" in prompt

    def test_flashcards_prompt_includes_note(self) -> None:
        prompt = flashcards_prompt(NOTE_BODY)
        assert NOTE_BODY in prompt
        assert "8 cards" in prompt

    def test_rewrite_prompt_includes_style(self) -> None:
        prompt = rewrite_prompt(NOTE_BODY, style="concise")
        assert NOTE_BODY in prompt
        assert "Style: concise" in prompt

    def test_rewrite_prompt_default_style(self) -> None:
        prompt = rewrite_prompt(NOTE_BODY)
        assert "Style: concise" in prompt

    def test_build_prompt_summarize(self) -> None:
        prompt = build_prompt("summarize", NOTE_BODY)
        assert "5 bullet points" in prompt

    def test_build_prompt_explain(self) -> None:
        prompt = build_prompt("explain", NOTE_BODY)
        assert "MSc AI" in prompt

    def test_build_prompt_questions(self) -> None:
        prompt = build_prompt("questions", NOTE_BODY)
        assert "short-answer" in prompt

    def test_build_prompt_flashcards(self) -> None:
        prompt = build_prompt("flashcards", NOTE_BODY)
        assert "8 cards" in prompt

    def test_build_prompt_rewrite_with_style(self) -> None:
        prompt = build_prompt("rewrite", NOTE_BODY, style="academic")
        assert "Style: academic" in prompt

    def test_build_prompt_unknown_action(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM action"):
            build_prompt("translate", NOTE_BODY)
