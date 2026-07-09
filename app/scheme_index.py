"""Scheme metadata loader and query-to-scheme resolution."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

COMMON_TOKENS = frozenset(
    {
        "hdfc",
        "mutual",
        "fund",
        "funds",
        "direct",
        "growth",
        "plan",
        "etf",
        "of",
        "the",
        "a",
        "an",
    }
)

MatchKind = Literal["scheme_name", "slug", "alias", "distinctive_tokens"]


@dataclass(frozen=True)
class SchemeMatch:
    slug: str
    scheme_name: str
    source_url: str
    category: str
    last_fetched_at: str
    match_kind: MatchKind
    score: int


def _normalize(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("defense", "defence")
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _distinctive_tokens(scheme_name: str) -> set[str]:
    return {token for token in _normalize(scheme_name).split() if token not in COMMON_TOKENS}


@lru_cache
def _load_metadata_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Scheme metadata not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_scheme_metadata(settings: Settings | None = None) -> dict[str, Any]:
    """Load scheme metadata index from disk (cached by path)."""
    settings = settings or get_settings()
    path = settings.scheme_metadata_path
    if not path.exists():
        logger.warning("Scheme metadata not found at %s — run ingestion first", path)
        return {"schemes": []}
    return _load_metadata_cached(str(path))


def get_scheme_by_slug(slug: str, settings: Settings | None = None) -> dict[str, Any] | None:
    """Return scheme dict for a slug, or None."""
    metadata = load_scheme_metadata(settings)
    for scheme in metadata.get("schemes", []):
        if scheme.get("slug") == slug:
            return scheme
    return None


def _squash(text: str) -> str:
    return _normalize(text).replace(" ", "")


def _score_scheme(query_norm: str, query_squash: str, scheme: dict[str, Any]) -> tuple[int, MatchKind | None]:
    scheme_name = scheme.get("scheme_name", "")
    name_norm = _normalize(scheme_name)
    name_squash = _squash(scheme_name)
    slug_norm = scheme.get("slug", "").replace("-", " ")
    slug_squash = scheme.get("slug", "").replace("-", "")
    candidates: list[tuple[int, MatchKind]] = []

    if name_norm and name_norm in query_norm:
        candidates.append((1000 + len(name_norm), "scheme_name"))

    if name_squash and name_squash in query_squash:
        candidates.append((950 + len(name_squash), "scheme_name"))

    if slug_norm and slug_norm in query_norm:
        candidates.append((400 + len(slug_norm), "slug"))

    if slug_squash and slug_squash in query_squash:
        candidates.append((420 + len(slug_squash), "slug"))

    for alias in scheme.get("aliases", []):
        alias_norm = _normalize(alias)
        alias_squash = _squash(alias)
        if alias_norm and alias_norm in query_norm:
            candidates.append((300 + len(alias_norm), "alias"))
        if alias_squash and alias_squash in query_squash:
            candidates.append((320 + len(alias_squash), "alias"))

    distinctive = _distinctive_tokens(scheme_name)
    query_tokens = set(query_norm.split())
    if distinctive:
        overlap = distinctive & query_tokens
        if overlap == distinctive:
            candidates.append((500 + len(distinctive), "distinctive_tokens"))
        elif len(overlap) >= 2:
            candidates.append((450 + len(overlap) * 40, "distinctive_tokens"))
        elif len(overlap) == 1 and len(distinctive) <= 2:
            token = next(iter(overlap))
            if len(token) >= 4:
                candidates.append((380 + len(token), "distinctive_tokens"))

    # Fuzzy: distinctive token appears inside squashed query (e.g. "midcap" → mid + cap fund)
    for token in distinctive:
        if len(token) >= 4 and token in query_squash:
            candidates.append((360 + len(token), "distinctive_tokens"))

    if not candidates:
        return 0, None
    return max(candidates, key=lambda item: item[0])


def resolve_scheme(query: str, settings: Settings | None = None) -> SchemeMatch | None:
    """
    Match user query to one scheme via name, slug, or alias.

    Returns None when no scheme matches or when only generic tokens (e.g. "hdfc fund")
    match multiple schemes equally (R-06, R-08).
    """
    if not query or not query.strip():
        return None

    metadata = load_scheme_metadata(settings)
    schemes = metadata.get("schemes", [])
    if not schemes:
        return None

    query_norm = _normalize(query)
    query_squash = _squash(query)
    scored: list[tuple[int, MatchKind, dict[str, Any]]] = []

    for scheme in schemes:
        score, kind = _score_scheme(query_norm, query_squash, scheme)
        if score > 0 and kind is not None:
            scored.append((score, kind, scheme))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_kind, top_scheme = scored[0]

    if len(scored) > 1 and scored[1][0] == top_score:
        return None

    return SchemeMatch(
        slug=top_scheme["slug"],
        scheme_name=top_scheme["scheme_name"],
        source_url=top_scheme["source_url"],
        category=top_scheme.get("category", ""),
        last_fetched_at=top_scheme.get("last_fetched_at", ""),
        match_kind=top_kind,
        score=top_score,
    )


def clear_scheme_cache() -> None:
    """Clear cached metadata (for tests)."""
    _load_metadata_cached.cache_clear()
