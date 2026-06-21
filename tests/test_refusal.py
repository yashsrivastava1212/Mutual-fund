"""Phase 4: refusal handler tests."""

from __future__ import annotations

from app.classifier import QueryType
from app.refusal import AMFI_EDUCATION_URL, DISCLAIMER, build_refusal


def test_advisory_refusal_structure() -> None:
    result = build_refusal(QueryType.ADVISORY)
    assert result["is_refusal"] is True
    assert result["citation_url"] == AMFI_EDUCATION_URL
    assert result["disclaimer"] == DISCLAIMER
    assert "investment advice" in result["answer"].lower()
    assert len(result["last_updated"]) == 10


def test_comparison_refusal_structure() -> None:
    result = build_refusal(QueryType.COMPARISON)
    assert result["is_refusal"] is True
    assert "compare" in result["answer"].lower()
    assert result["citation_url"].startswith("https://")
