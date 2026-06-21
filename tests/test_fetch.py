"""Tests for ingestion.fetch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from config.settings import get_settings
from ingestion.fetch import fetch_all, fetch_scheme, fetch_url


def test_fetch_url_success() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html>ok</html>"

    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("ingestion.fetch.httpx.Client", return_value=mock_client):
        status, html, error = fetch_url("https://groww.in/mutual-funds/test")

    assert status == 200
    assert html == "<html>ok</html>"
    assert error is None


def test_fetch_url_retries_on_503() -> None:
    fail_response = MagicMock(status_code=503, text="")
    ok_response = MagicMock(status_code=200, text="<html>recovered</html>")

    mock_client = MagicMock()
    mock_client.get.side_effect = [fail_response, ok_response]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("ingestion.fetch.httpx.Client", return_value=mock_client):
        with patch("ingestion.fetch.time.sleep"):
            status, html, error = fetch_url(
                "https://groww.in/mutual-funds/test",
                retry_count=2,
                retry_base_delay_seconds=0,
            )

    assert status == 200
    assert html == "<html>recovered</html>"
    assert error is None
    assert mock_client.get.call_count == 2


def test_fetch_url_non_retryable_404() -> None:
    mock_response = MagicMock(status_code=404, text="not found")
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with patch("ingestion.fetch.httpx.Client", return_value=mock_client):
        status, html, error = fetch_url("https://groww.in/mutual-funds/missing")

    assert status == 404
    assert html is None
    assert error == "HTTP 404"
    assert mock_client.get.call_count == 1


def test_fetch_scheme_writes_raw_files(tmp_path: Path) -> None:
    from dataclasses import replace

    settings = replace(get_settings(), data_raw_dir=tmp_path)
    scheme = {
        "slug": "test-scheme",
        "scheme_name": "Test Scheme",
        "source_url": "https://groww.in/mutual-funds/test-scheme",
    }

    with patch(
        "ingestion.fetch.fetch_url",
        return_value=(200, "<html><body>scheme</body></html>", None),
    ):
        record = fetch_scheme(scheme, settings, rate_limit_seconds=0)

    assert record.success is True
    assert (tmp_path / "test-scheme.html").exists()
    assert (tmp_path / "test-scheme.meta.json").exists()


def test_fetch_all_rate_limits_between_requests() -> None:
    scheme_a = {"slug": "a", "scheme_name": "A", "source_url": "https://example.com/a"}
    scheme_b = {"slug": "b", "scheme_name": "B", "source_url": "https://example.com/b"}

    with patch("ingestion.fetch.fetch_scheme") as mock_fetch_scheme:
        mock_fetch_scheme.return_value = MagicMock(success=True)
        fetch_all(schemes=[scheme_a, scheme_b], rate_limit_seconds=1.5)

    assert mock_fetch_scheme.call_count == 2
    first_call = mock_fetch_scheme.call_args_list[0]
    second_call = mock_fetch_scheme.call_args_list[1]
    assert first_call.kwargs["sleep_after"] is True
    assert second_call.kwargs["sleep_after"] is False
    assert first_call.kwargs["rate_limit_seconds"] == 1.5


def test_fetch_scheme_sleeps_when_sleep_after_enabled(tmp_path: Path) -> None:
    from dataclasses import replace

    settings = replace(get_settings(), data_raw_dir=tmp_path)
    scheme = {
        "slug": "test-scheme",
        "scheme_name": "Test Scheme",
        "source_url": "https://groww.in/mutual-funds/test-scheme",
    }

    with patch(
        "ingestion.fetch.fetch_url",
        return_value=(200, "<html>ok</html>", None),
    ):
        with patch("ingestion.fetch.time.sleep") as mock_sleep:
            fetch_scheme(scheme, settings, sleep_after=True, rate_limit_seconds=2.0)

    mock_sleep.assert_called_once_with(2.0)
