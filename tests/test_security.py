"""Phase 4/5: security and rate limit tests."""

from __future__ import annotations

from app.rate_limit import RateLimiter
from app.security import detect_pii, sanitize_message, validate_message


def test_sanitize_message_strips_control_chars() -> None:
    assert sanitize_message("  hello   world  ") == "hello world"


def test_detect_pii_pan() -> None:
    assert detect_pii("My PAN is ABCDE1234F") == "PAN number"


def test_detect_pii_email() -> None:
    assert detect_pii("Contact user@example.com") == "email address"


def test_detect_pii_phone() -> None:
    assert detect_pii("Call me at 9876543210") == "phone number"


def test_no_false_positive_on_nifty() -> None:
    assert detect_pii("Nifty 50 crossed 22000") is None


def test_validate_message_rejects_pii() -> None:
    _, error = validate_message("My PAN is ABCDE1234F, expense ratio?")
    assert error is not None
    assert "personal information" in error


def test_validate_message_rejects_empty() -> None:
    _, error = validate_message("   ")
    assert error == "Message cannot be empty."


def test_rate_limiter_blocks_burst() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is True
    assert limiter.check("1.2.3.4") is False
