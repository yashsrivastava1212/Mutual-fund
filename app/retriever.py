"""Scheme-aware retriever — Phase 3 three-stage hybrid."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import lancedb

from app.scheme_index import SchemeMatch, resolve_scheme
from app.section_intent import SectionIntent, detect_section_intent
from config.settings import Settings, get_settings
from ingestion.embeddings import embed_query

logger = logging.getLogger(__name__)

CHUNKS_TABLE_NAME = "chunks"
FETCH_K = 5
DEFAULT_TOP_K = 3
SECTION_SCORE_BOOST = 0.15


@lru_cache
def _open_table(db_path_str: str):
    db = lancedb.connect(db_path_str)
    return db.open_table(CHUNKS_TABLE_NAME)


def clear_retriever_cache() -> None:
    """Clear cached LanceDB table handle (for tests)."""
    _open_table.cache_clear()


def _distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, 1.0 - float(distance))


def _row_to_chunk(row: dict[str, Any], scheme: SchemeMatch, score: float) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "scheme_name": scheme.scheme_name,
        "source_url": scheme.source_url,
        "section": row["section"],
        "text": row["text"],
        "last_updated": row["last_updated"],
        "score": round(score, 4),
    }


def _rerank(
    rows: list[dict[str, Any]],
    section_intent: SectionIntent | None,
) -> list[tuple[dict[str, Any], float]]:
    ranked: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        score = _distance_to_score(row.get("_distance"))
        if section_intent and row.get("section") == section_intent.section:
            score += SECTION_SCORE_BOOST
        ranked.append((row, score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def _search_chunks(
    table,
    query_vector: list[float],
    slug: str,
    section: str | None,
) -> list[dict[str, Any]]:
    base_filter = f"slug = '{slug}'"
    if section:
        section_filter = f"{base_filter} AND section = '{section}'"
        results = table.search(query_vector).where(section_filter).limit(FETCH_K).to_list()
        if results:
            return results
    return table.search(query_vector).where(base_filter).limit(FETCH_K).to_list()


def retrieve(
    message: str,
    top_k: int = DEFAULT_TOP_K,
    settings: Settings | None = None,
) -> list[dict]:
    """
    Retrieve top-k chunks for a user message.

    Pipeline: scheme resolution → section intent → LanceDB BGE search → re-rank.
    Returns [] when no scheme matches.
    """
    settings = settings or get_settings()
    scheme = resolve_scheme(message, settings)
    if scheme is None:
        logger.debug("No scheme resolved for query")
        return []

    section_intent = detect_section_intent(message)
    section_filter: str | None = None
    if section_intent and section_intent.confidence == "high":
        section_filter = section_intent.section

    try:
        table = _open_table(str(settings.lance_db_uri))
    except Exception as exc:
        logger.error("Failed to open LanceDB table: %s", exc)
        return []

    query_vector = embed_query(message, settings)
    rows = _search_chunks(table, query_vector, scheme.slug, section_filter)
    ranked = _rerank(rows, section_intent)

    effective_k = top_k
    if section_intent and section_intent.section == "fund_management":
        effective_k = min(3, top_k)

    seen_ids: set[str] = set()
    chunks: list[dict] = []
    for row, score in ranked:
        chunk_id = row["id"]
        if chunk_id in seen_ids:
            continue
        seen_ids.add(chunk_id)
        chunks.append(_row_to_chunk(row, scheme, score))
        if len(chunks) >= effective_k:
            break

    return chunks
