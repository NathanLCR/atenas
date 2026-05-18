"""SQLite-friendly lexical scoring helpers for retrieval."""

from __future__ import annotations

import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]*")

STOPWORDS = frozenset({
    "a",
    "about",
    "after",
    "all",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "say",
    "says",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
})


def tokenize(text: str) -> list[str]:
    """Return normalized retrieval tokens with common question words removed."""

    return [
        token
        for token in TOKEN_RE.findall(text.lower())
        if len(token) >= 2 and token not in STOPWORDS
    ]


def query_terms(query: str) -> list[str]:
    """Return de-duplicated query terms in first-seen order."""

    terms: list[str] = []
    seen: set[str] = set()
    for token in tokenize(query):
        if token not in seen:
            seen.add(token)
            terms.append(token)
    return terms


def term_counts(text: str) -> Counter[str]:
    return Counter(tokenize(text))


def lexical_score(query: str, title: str, text: str) -> float:
    """Score a chunk by deterministic sparse lexical overlap."""

    terms = query_terms(query)
    if not terms:
        return 0.0

    title_counts = term_counts(title)
    text_counts = term_counts(text)
    matched_terms = [term for term in terms if title_counts[term] or text_counts[term]]
    if not matched_terms:
        return 0.0

    score = 0.0
    for term in matched_terms:
        score += 3.0
        score += min(text_counts[term], 5) * 0.8
        score += min(title_counts[term], 3) * 2.0

    normalized_query = " ".join(terms)
    normalized_title = " ".join(tokenize(title))
    normalized_text = " ".join(tokenize(text))
    if normalized_query and normalized_query in normalized_title:
        score += 8.0
    if normalized_query and normalized_query in normalized_text:
        score += 6.0
    return score
