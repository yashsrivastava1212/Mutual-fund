"""Phase 6: Web UI tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXAMPLE_SNIPPETS = [
    "What is the expense ratio of HDFC Mid Cap Fund Direct Growth?",
    "What is the exit load on HDFC Defence Fund Direct Growth?",
    "Who manages HDFC Gold ETF Fund of Fund Direct Plan Growth?",
]


def test_serve_ui_index() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "HDFC Scheme Terminal" in body
    assert "Facts-only. No investment advice." in body
    assert "Do not share personal information" not in body


def test_ui_static_app_js() -> None:
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"] or "text/javascript" in response.headers["content-type"]
    assert "/api/chat" in response.text
    assert "/api/corpus" in response.text


def test_ui_contains_example_questions() -> None:
    js = client.get("/ui/app.js")
    assert js.status_code == 200
    body = js.text
    for snippet in EXAMPLE_SNIPPETS:
        assert snippet in body


def test_ui_trading_terminal_elements() -> None:
    response = client.get("/")
    body = response.text
    assert 'id="scheme-list"' in body
    assert 'id="ticker"' in body
    assert 'id="market-clock"' in body
    assert 'id="quick-actions"' in body


def test_ui_chat_form_elements() -> None:
    response = client.get("/")
    body = response.text
    assert 'id="chat-form"' in body
    assert 'id="message-input"' in body
    assert 'id="example-questions"' in body
