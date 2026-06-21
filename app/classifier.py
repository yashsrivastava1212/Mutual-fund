"""Query classifier — rule-based advisory/comparison detection."""

from __future__ import annotations

import re
from enum import Enum

ADVISORY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bshould i\b",
        r"\bshould we\b",
        r"\brecommend(?:ation|ed|s)?\b",
        r"\b(?:buy|sell|hold)\b",
        r"\bgood time to (?:buy|invest|sell)\b",
        r"\bsuitable for\b",
        r"\bwill .{0,40}\b(?:give|return|yield)\b",
        r"\binvest (?:in|karna|karu)\b",
        r"\b(?:adding|add) .{0,30}\bportfolio\b",
        r"\b(?:retirement|conservative investor)\b",
        r"\bput(?:ting)? .{0,20}\b(?:in|into)\b",
        r"\bwhich (?:fund|scheme) (?:to|should)\b",
        r"\bworry about\b",
        r"\bbest fund ever\b",
        r"\binvest karna\b",
        r"\bkya .{0,40}\binvest\b",
    )
)

COMPARISON_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bwhich is better\b",
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\b(?:vs\.?|versus)\b",
        r"\bbetter than\b",
        r"\bwhich to pick\b",
        r"\bwhich one (?:to|should)\b",
        r"\b(?:lowest|highest|best|worst) .{0,30}\b(?:expense|ratio|return|fund|scheme)\b",
        r"\bcompare .{0,40}\b(?:and|with|to)\b",
        r"\bhow does .{0,40}\bcompare\b",
        r"\b(?:mid|small|large) cap vs\b",
    )
)


class QueryType(str, Enum):
    FACTUAL = "factual"
    ADVISORY = "advisory"
    COMPARISON = "comparison"


def classify_query(message: str) -> QueryType:
    """Classify user message using rule-based patterns (comparison checked before advisory)."""
    if not message or not message.strip():
        return QueryType.FACTUAL

    normalized = message.strip()

    for pattern in COMPARISON_PATTERNS:
        if pattern.search(normalized):
            return QueryType.COMPARISON

    for pattern in ADVISORY_PATTERNS:
        if pattern.search(normalized):
            return QueryType.ADVISORY

    return QueryType.FACTUAL
