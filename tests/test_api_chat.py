"""Phase 5: API integration tests for POST /api/chat."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMCompletion
from app.main import app, rate_limiter

client = TestClient(app)

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


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    rate_limiter.reset()
    yield
    rate_limiter.reset()


def test_chat_advisory_refusal_no_retrieval() -> None:
    with patch("app.chat.retrieve") as mock_retrieve:
        response = client.post(
            "/api/chat",
            json={"message": "Should I invest in HDFC Mid Cap Fund?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is True
    assert "amfiindia.com" in data["citation_url"]
    mock_retrieve.assert_not_called()


def test_chat_comparison_refusal() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Which is better: HDFC Mid Cap or HDFC Small Cap?"},
    )
    assert response.status_code == 200
    assert response.json()["is_refusal"] is True


def test_chat_factual_with_mocked_pipeline() -> None:
    mock_llm = MagicMock()
    mock_llm.complete_with_retry.return_value = LLMCompletion(
        content="The expense ratio is 0.77%.",
        model="test-model",
    )

    with (
        patch("app.chat.retrieve", return_value=SAMPLE_CHUNKS),
        patch("app.chat._llm_available", return_value=True),
        patch("app.chat.generate_answer", return_value="The expense ratio is 0.77%."),
    ):
        response = client.post(
            "/api/chat",
            json={"message": "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is False
    assert data["citation_url"].startswith("https://groww.in/mutual-funds/")
    assert "2026-06-09" in data["last_updated"]
    assert data["disclaimer"] == "Facts-only. No investment advice."


def test_chat_missing_message_returns_422() -> None:
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_empty_message_returns_400() -> None:
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400


def test_chat_pii_rejection() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "My PAN is ABCDE1234F — expense ratio mid cap?"},
    )
    assert response.status_code == 400
    assert "personal information" in response.json()["detail"]


def test_chat_rate_limit() -> None:
    rate_limiter.max_requests = 2
    message = {"message": "Should I invest in HDFC Mid Cap?"}
    assert client.post("/api/chat", json=message).status_code == 200
    assert client.post("/api/chat", json=message).status_code == 200
    assert client.post("/api/chat", json=message).status_code == 429


def test_chat_insufficient_context() -> None:
    with patch("app.chat.retrieve", return_value=[]):
        response = client.post(
            "/api/chat",
            json={"message": "What is the expense ratio?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_refusal"] is False
    assert data["out_of_corpus"] is True
    assert "please ask details about the given mutual funds only" in data["answer"].lower()
