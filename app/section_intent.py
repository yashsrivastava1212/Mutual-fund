"""Rule-based section intent detection for retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Confidence = Literal["high", "medium"]

# (section, keywords/phrases, confidence) — longer phrases matched first via best keyword length
SECTION_RULES: list[tuple[str, tuple[str, ...], Confidence]] = [
    ("expense_ratio", (
        "expense ratio", "total expense ratio", "ter", "annual charges",
        "management fee", "management fees", "fund charges", "cost of fund",
        "how much does it cost", "charges for managing",
    ), "high"),
    ("exit_load", (
        "exit load", "redemption charge", "redemption fee", "withdrawal charge",
        "charges on exit", "charges if i sell", "charges if i redeem", "early exit",
    ), "high"),
    ("minimum_sip", (
        "minimum sip", "sip amount", "min sip", "monthly sip", "sip minimum",
        "least sip", "smallest sip",
    ), "high"),
    ("minimum_investment", (
        "minimum investment", "lumpsum", "lump sum", "min investment",
        "minimum amount", "least investment", "smallest investment",
    ), "high"),
    ("riskometer", ("riskometer", "risk level", "risk rating", "how risky"), "high"),
    ("benchmark", ("benchmark", "index tracked", "tracks which index", "compared to which index"), "high"),
    ("fund_management", (
        "fund manager", "fund managers", "who manages", "who manage", "who runs",
        "managed by", "portfolio manager", "fund lead", "tenure", "manager name",
    ), "high"),
    ("stamp_duty", ("stamp duty",), "high"),
    ("scheme_overview", (
        "objective", "launch date", "category", "overview", "inception",
        "what kind of fund", "investment objective",
    ), "medium"),
    ("riskometer", ("risk profile",), "medium"),
    ("benchmark", ("index", "tracks"), "medium"),
    ("fund_management", ("manager", "managers"), "medium"),
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
