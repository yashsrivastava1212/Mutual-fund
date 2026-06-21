"""Phase 1: API health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["corpus_schemes"] == 5
    assert "llm_model" in data
    assert data["llm_provider"] == "groq"


def test_corpus_endpoint() -> None:
    response = client.get("/api/corpus")
    assert response.status_code == 200
    data = response.json()
    assert len(data["schemes"]) == 5
