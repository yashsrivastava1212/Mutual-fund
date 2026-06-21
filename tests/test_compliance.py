"""Phase 8: compliance and end-to-end API tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_CHUNKS = [
    {
        "id": "hdfc-mid-cap-fund-direct-growth#expense_ratio#0",
        "slug": "hdfc-mid-cap-fund-direct-growth",
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "section": "expense_ratio",
        "text": "Expense ratio: 0.77%",
        "last_updated": "2026-06-09",
        "score": 0.9,
    }
]


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    from app import main as main_module

    main_module.rate_limiter.reset()
    yield
    main_module.rate_limiter.reset()


@pytest.mark.parametrize(
    "message",
    [
        "Should I invest in HDFC Mid Cap Fund?",
        "Recommend a fund for retirement",
        "Which is better: HDFC Mid Cap or HDFC Small Cap?",
        "Compare exit loads of mid cap and defence fund",
    ],
)
def test_advisory_and_comparison_refused(message: str) -> None:
    with patch("app.chat.retrieve") as mock_retrieve:
        response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is True
    assert data["citation_url"].startswith("https://")
    assert data["last_updated"]
    assert data["disclaimer"] == "Facts-only. No investment advice."
    mock_retrieve.assert_not_called()


def test_pii_rejected() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "My PAN is ABCDE1234F — expense ratio?"},
    )
    assert response.status_code == 400


def test_factual_response_has_citation_and_footer() -> None:
    with (
        patch("app.chat.retrieve", return_value=SAMPLE_CHUNKS),
        patch("app.chat._llm_available", return_value=False),
    ):
        response = client.post(
            "/api/chat",
            json={"message": "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is False
    assert data["citation_url"].startswith("https://groww.in/mutual-funds/")
    assert data["last_updated"]
    assert "Last updated from sources:" in data["answer"]


def test_health_and_corpus_endpoints() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["corpus_schemes"] == 5

    corpus = client.get("/api/corpus")
    assert corpus.status_code == 200
    assert len(corpus.json()["schemes"]) == 5
