"""Chat orchestration — classifier, retrieval, RAG, and refusals."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.classifier import QueryType, classify_query
from app.formatter import format_from_chunks, format_response
from app.generator import build_context_block, generate_answer
from app.llm import LLMClient
from app.refusal import AMFI_EDUCATION_URL, build_refusal
from app.retriever import retrieve
from app.validator import validate_response

logger = logging.getLogger(__name__)

INSUFFICIENT_CONTEXT_ANSWER = (
    "I could not match your question to one of the five HDFC schemes in my corpus. "
    "Please name the scheme (for example, HDFC Mid Cap Fund Direct Growth) and ask about "
    "expense ratio, exit load, minimum SIP, benchmark, riskometer, or fund managers."
)

FALLBACK_ANSWER = (
    "I am unable to provide a verified answer from the indexed sources. "
    "Please refer to the scheme page for the latest factual information."
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def handle_factual_query(
    message: str,
    *,
    llm: LLMClient | None = None,
) -> dict:
    """Run retrieval → generation → validation for a factual query."""
    chunks = retrieve(message)
    if not chunks:
        return format_response(
            INSUFFICIENT_CONTEXT_ANSWER,
            AMFI_EDUCATION_URL,
            _today_iso(),
            is_refusal=False,
        )

    context = build_context_block(chunks)
    citation_url = chunks[0]["source_url"]

    try:
        if llm is not None or _llm_available():
            draft = generate_answer(message, chunks, llm=llm)
        else:
            draft = _extractive_fallback(chunks)
    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        draft = FALLBACK_ANSWER

    if not validate_response(draft, citation_url, context):
        logger.warning("Validation failed; using fallback answer")
        draft = FALLBACK_ANSWER
        if not validate_response(draft, citation_url, context):
            return format_from_chunks(FALLBACK_ANSWER, chunks)

    return format_from_chunks(draft, chunks)


def _llm_available() -> bool:
    from config.settings import get_settings

    return get_settings().llm_configured


def _extractive_fallback(chunks: list[dict]) -> str:
    """Return chunk text when Groq is not configured (tests / offline)."""
    top = chunks[0]
    text = top["text"]
    if "| Section:" in text:
        text = text.split("\n", 1)[-1].strip()
    return text[:500]


def handle_chat(message: str, *, llm: LLMClient | None = None) -> dict:
    """Route message through classifier → refusal or RAG path."""
    query_type = classify_query(message)

    if query_type in (QueryType.ADVISORY, QueryType.COMPARISON):
        return build_refusal(query_type)

    return handle_factual_query(message, llm=llm)
