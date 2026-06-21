"""Tests for ingestion.run orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ingestion.run import run_ingestion


def test_run_ingestion_skip_fetch() -> None:
    with patch("ingestion.run.fetch_all") as mock_fetch:
        with patch("ingestion.run.parse_all", return_value=[MagicMock()]):
            with patch("ingestion.run.chunk_all", return_value=[MagicMock(), MagicMock()]):
                with patch(
                    "ingestion.run.index_all",
                    return_value={"chunk_count": 2, "scheme_count": 5},
                ):
                    summary = run_ingestion(skip_fetch=True)

    mock_fetch.assert_not_called()
    assert summary["steps"]["parse"]["schemes_parsed"] == 1
    assert summary["steps"]["chunk"]["chunk_count"] == 2
    assert summary["steps"]["index"]["chunk_count"] == 2


def test_run_ingestion_fails_on_fetch_error() -> None:
    failed = MagicMock(success=False, slug="bad-scheme")
    with patch("ingestion.run.fetch_all", return_value=[failed]):
        try:
            run_ingestion(skip_fetch=False)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "bad-scheme" in str(exc)
