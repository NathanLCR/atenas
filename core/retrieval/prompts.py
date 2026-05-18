"""Prompt construction for source-grounded retrieval answers."""

from __future__ import annotations

from core.retrieval.models import RetrievedSource


def build_answer_prompt(question: str, sources: list[RetrievedSource]) -> str:
    source_blocks = "\n\n".join(
        "[{label}] {title}\n{text}".format(
            label=source.chunk_label,
            title=source.title,
            text=source.text,
        )
        for source in sources
    )
    return f"""You are answering a student's question using only registered Atenas notes/files.

Rules:
- Use only the sources below.
- Cite source labels inline like [N1.1] or [F2.1].
- If the sources do not support part of the answer, say that the notes/files do not say.
- Keep the answer concise and study-focused.

Question:
{question}

Sources:
{source_blocks}

Answer:"""
