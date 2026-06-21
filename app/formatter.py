"""Response formatter — enforces API output contract."""

from __future__ import annotations

import re

from app.refusal import DISCLAIMER
from app.validator import truncate_to_max_sentences

_URL_IN_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)


def _strip_urls(text: str) -> str:
    return _URL_IN_TEXT.sub("", text).strip()


def _latest_date(dates: list[str]) -> str:
    if not dates:
        return ""
    return max(dates)


def format_response(
    answer: str,
    citation_url: str,
    last_updated: str,
    is_refusal: bool = False,
) -> dict:
    """Format structured JSON response for the UI."""
    body = truncate_to_max_sentences(_strip_urls(answer.strip()))
    footer = f"Last updated from sources: {last_updated}" if last_updated else ""
    full_answer = f"{body} {footer}".strip() if footer else body

    return {
        "answer": full_answer,
        "citation_url": citation_url,
        "last_updated": last_updated,
        "is_refusal": is_refusal,
        "disclaimer": DISCLAIMER,
    }


def format_from_chunks(answer: str, chunks: list[dict], *, is_refusal: bool = False) -> dict:
    """Format a factual response using chunk metadata for citation and date."""
    if not chunks:
        raise ValueError("chunks required for factual formatting")

    citation_url = chunks[0]["source_url"]
    last_updated = _latest_date([chunk["last_updated"] for chunk in chunks])
    return format_response(answer, citation_url, last_updated, is_refusal=is_refusal)
