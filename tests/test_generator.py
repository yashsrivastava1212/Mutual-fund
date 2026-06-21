"""Phase 4: generator, validator, and formatter tests."""

from __future__ import annotations

from app.formatter import format_from_chunks, format_response
from app.generator import build_context_block, build_user_prompt
from app.validator import count_sentences, truncate_to_max_sentences, validate_response

SAMPLE_CHUNKS = [
    {
        "id": "hdfc-mid-cap-fund-direct-growth#expense_ratio#0",
        "slug": "hdfc-mid-cap-fund-direct-growth",
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "section": "expense_ratio",
        "text": "HDFC Mid Cap Fund Direct Growth | Section: expense_ratio\nExpense ratio: 0.77%",
        "last_updated": "2026-06-09",
        "score": 0.9,
    }
]


def test_build_context_block_includes_metadata() -> None:
    block = build_context_block(SAMPLE_CHUNKS)
    assert "expense_ratio" in block
    assert "0.77%" in block
    assert "groww.in" in block


def test_build_user_prompt_includes_question() -> None:
    prompt = build_user_prompt("What is the expense ratio?", SAMPLE_CHUNKS)
    assert "What is the expense ratio?" in prompt
    assert "Context:" in prompt


def test_count_sentences() -> None:
    assert count_sentences("One. Two. Three. Four.") == 4
    assert count_sentences("Single sentence") == 1


def test_truncate_to_max_sentences() -> None:
    text = "First. Second. Third. Fourth."
    assert count_sentences(truncate_to_max_sentences(text, 3)) == 3


def test_validate_response_accepts_grounded_answer() -> None:
    context = build_context_block(SAMPLE_CHUNKS)
    answer = "The expense ratio is 0.77%."
    assert validate_response(
        answer,
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        context,
    )


def test_validate_response_rejects_advice() -> None:
    context = build_context_block(SAMPLE_CHUNKS)
    assert not validate_response(
        "You should buy this fund.",
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        context,
    )


def test_validate_response_rejects_hallucinated_number() -> None:
    context = build_context_block(SAMPLE_CHUNKS)
    assert not validate_response(
        "The expense ratio is 9.99%.",
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        context,
    )


def test_format_response_includes_footer() -> None:
    result = format_response(
        "The expense ratio is 0.77%.",
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "2026-06-09",
    )
    assert result["is_refusal"] is False
    assert "Last updated from sources: 2026-06-09" in result["answer"]
    assert result["disclaimer"] == "Facts-only. No investment advice."


def test_format_from_chunks_uses_citation() -> None:
    result = format_from_chunks("The expense ratio is 0.77%.", SAMPLE_CHUNKS)
    assert result["citation_url"] == SAMPLE_CHUNKS[0]["source_url"]
    assert result["last_updated"] == "2026-06-09"
