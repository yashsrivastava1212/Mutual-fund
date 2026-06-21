"""Post-generation output validator."""

from __future__ import annotations

import re

from app.corpus_urls import get_corpus_source_urls

MAX_SENTENCES = 3

_BANNED_ADVICE = re.compile(
    r"\b(?:should invest|recommend|buy|sell|hold|better fund|best fund|worst fund|"
    r"compare|versus|vs\.?|suitable for|good time to)\b",
    re.IGNORECASE,
)

_URL_IN_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def count_sentences(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    parts = _SENTENCE_SPLIT.split(stripped)
    return len([part for part in parts if part.strip()])


def truncate_to_max_sentences(text: str, max_sentences: int = MAX_SENTENCES) -> str:
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences])


def _numbers_in_text(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def validate_response(answer: str, citation_url: str, context: str) -> bool:
    """
    Validate grounding and compliance.

    Returns True if the answer passes all checks.
    """
    if not answer or not answer.strip():
        return False

    if count_sentences(answer) > MAX_SENTENCES:
        return False

    if _BANNED_ADVICE.search(answer):
        return False

    if _URL_IN_TEXT.search(answer):
        return False

    allowed_urls = get_corpus_source_urls()
    if citation_url not in allowed_urls:
        return False

    answer_numbers = _numbers_in_text(answer)
    if answer_numbers:
        context_numbers = _numbers_in_text(context)
        if not answer_numbers.issubset(context_numbers):
            return False

    return True
