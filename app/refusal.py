"""Templated refusal responses for advisory and comparison queries."""

from __future__ import annotations

from datetime import datetime, timezone

from app.classifier import QueryType

AMFI_EDUCATION_URL = "https://www.amfiindia.com/investor/knowledge-center-info?faqs"
DISCLAIMER = "Facts-only. No investment advice."

ADVISORY_ANSWER = (
    "I can only answer factual questions about HDFC schemes in my corpus, such as expense ratio, "
    "exit load, minimum SIP, benchmark, riskometer, or fund manager details. "
    "I cannot provide investment advice or recommend which fund to choose."
)

COMPARISON_ANSWER = (
    "I cannot compare funds or rank schemes. I can answer factual questions about one HDFC scheme "
    "at a time, such as expense ratio, exit load, or fund manager details for a named scheme."
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def build_refusal(query_type: QueryType) -> dict[str, str]:
    """Build refusal content without retrieval or LLM."""
    if query_type == QueryType.COMPARISON:
        answer = COMPARISON_ANSWER
    else:
        answer = ADVISORY_ANSWER

    return {
        "answer": answer,
        "citation_url": AMFI_EDUCATION_URL,
        "last_updated": _today_iso(),
        "is_refusal": True,
        "disclaimer": DISCLAIMER,
    }
