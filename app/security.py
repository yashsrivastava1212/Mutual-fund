"""Input sanitization and PII detection."""

from __future__ import annotations

import re

MAX_MESSAGE_LENGTH = 2000

_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?:\+91[\s-]?|0)?[6-9]\d{9}\b")
_OTP = re.compile(r"\botp\s*:?\s*\d{4,8}\b", re.IGNORECASE)
_ACCOUNT = re.compile(
    r"\b(?:account|a/c|ac)\s*(?:no|number|#)?\s*:?\s*\d{9,18}\b",
    re.IGNORECASE,
)

_PII_CHECKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_PAN, "PAN number"),
    (_AADHAAR, "Aadhaar number"),
    (_EMAIL, "email address"),
    (_PHONE, "phone number"),
    (_OTP, "OTP"),
    (_ACCOUNT, "bank account number"),
)


def sanitize_message(message: str) -> str:
    """Normalize whitespace and strip control characters."""
    cleaned = "".join(ch for ch in message if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return " ".join(cleaned.split())


def detect_pii(message: str) -> str | None:
    """Return a human-readable PII type if detected, else None."""
    for pattern, label in _PII_CHECKS:
        if pattern.search(message):
            return label
    return None


def validate_message(message: str, *, max_length: int = MAX_MESSAGE_LENGTH) -> tuple[str, str | None]:
    """
    Sanitize and validate a user message.

    Returns (sanitized_message, error_detail). error_detail is set for PII or length violations.
    """
    sanitized = sanitize_message(message)
    if not sanitized:
        return sanitized, "Message cannot be empty."

    if len(sanitized) > max_length:
        return sanitized, f"Message exceeds maximum length of {max_length} characters."

    pii = detect_pii(sanitized)
    if pii:
        return sanitized, f"Message contains personal information ({pii}). Please remove it and try again."

    return sanitized, None
