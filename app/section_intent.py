"""Rule-based section intent detection for retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Confidence = Literal["high", "medium"]

SECTION_RULES: list[tuple[str, tuple[str, ...], Confidence]] = [
    ("expense_ratio", ("expense ratio", "ter"), "high"),
    ("exit_load", ("exit load", "redemption charge"), "high"),
    ("minimum_sip", ("minimum sip", "sip amount", "min sip"), "high"),
    ("minimum_investment", ("minimum investment", "lumpsum", "lump sum", "min investment"), "high"),
    ("riskometer", ("riskometer", "risk level"), "high"),
    ("benchmark", ("benchmark", "index tracked"), "medium"),
    ("fund_management", ("fund manager", "fund managers", "who manages", "who manage", "tenure"), "high"),
    ("stamp_duty", ("stamp duty",), "high"),
    ("scheme_overview", ("objective", "launch date", "category", "overview", "inception"), "medium"),
    ("riskometer", ("risk",), "medium"),
    ("benchmark", ("index",), "medium"),
    ("fund_management", ("manager",), "medium"),
]


@dataclass(frozen=True)
class SectionIntent:
    section: str
    confidence: Confidence
    matched_keyword: str


def _normalize(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def detect_section_intent(query: str) -> SectionIntent | None:
    """Detect target section from keyword rules. Returns None if no signal."""
    if not query or not query.strip():
        return None

    normalized = _normalize(query)
    best: SectionIntent | None = None

    for section, keywords, confidence in SECTION_RULES:
        for keyword in keywords:
            if keyword in normalized:
                candidate = SectionIntent(
                    section=section,
                    confidence=confidence,
                    matched_keyword=keyword,
                )
                if best is None or len(keyword) > len(best.matched_keyword):
                    best = candidate

    return best
