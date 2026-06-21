"""Phase 7: daily scheduler tests."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from config.settings import get_settings
from scheduler.daily import run_scheduled_ingestion
from scheduler.status import read_status, write_run_result


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_write_and_read_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_INDEX_DIR", str(tmp_path))
    get_settings.cache_clear()
    from dataclasses import replace

    settings = replace(get_settings(), data_index_dir=tmp_path)

    write_run_result(success=True, summary={"steps": {"chunk": {"chunk_count": 51}}}, settings=settings)
    status = read_status(settings)
    assert status["last_success"] is not None
    assert len(status["runs"]) == 1


def test_run_scheduled_ingestion_success(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_ingestion():
        calls["n"] += 1
        return {"steps": {"chunk": {"chunk_count": 51}, "index": {"chunk_count": 51}}}

    with (
        patch("scheduler.daily.run_ingestion", side_effect=fake_ingestion),
        patch("scheduler.daily.clear_runtime_caches"),
        patch("scheduler.daily.write_run_result", return_value={}),
    ):
        summary = run_scheduled_ingestion()
    assert calls["n"] == 1
    assert summary["steps"]["chunk"]["chunk_count"] == 51


def test_run_scheduled_ingestion_retries_once(monkeypatch) -> None:
    monkeypatch.setenv("SCHEDULER_MAX_RETRIES", "2")
    monkeypatch.setenv("SCHEDULER_RETRY_DELAY_SECONDS", "0")
    get_settings.cache_clear()

    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("network blip")
        return {"steps": {"chunk": {"chunk_count": 51}}}

    with (
        patch("scheduler.daily.run_ingestion", side_effect=flaky),
        patch("scheduler.daily.clear_runtime_caches"),
        patch("scheduler.daily.write_run_result", return_value={}),
    ):
        run_scheduled_ingestion()

    assert attempts["n"] == 2


def test_scheduler_status_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert "next_schedule" in data
    assert data["next_schedule"]["timezone"] == "Asia/Kolkata"
    assert data["next_schedule"]["hour"] == 10
