"""Embed chunks and index into LanceDB with scheme metadata."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataclasses import replace

import lancedb

from config.embedding_models import (
    compute_chunk_stats,
    get_model_spec,
    resolve_embedding_model,
)
from config.settings import Settings, get_settings, load_corpus
from ingestion.embeddings import embed_documents
from ingestion.schemas import ChunkRecord

logger = logging.getLogger(__name__)

CHUNKS_TABLE_NAME = "chunks"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_chunk_records(settings: Settings) -> list[ChunkRecord]:
    """Load all chunk records from data/processed/chunks/."""
    chunks_dir = settings.data_chunks_dir
    if not chunks_dir.exists():
        return []

    records: list[ChunkRecord] = []
    for chunk_file in sorted(chunks_dir.glob("*.json")):
        payload = json.loads(chunk_file.read_text(encoding="utf-8"))
        for item in payload.get("chunks", []):
            records.append(
                ChunkRecord(
                    id=item["id"],
                    slug=item["slug"],
                    scheme_name=item["scheme_name"],
                    source_url=item["source_url"],
                    section=item["section"],
                    text=item["text"],
                    last_updated=item["last_updated"],
                    chunk_index=item.get("chunk_index", 0),
                )
            )
    return records


def build_scheme_metadata(
    corpus: dict[str, Any],
    chunks: list[ChunkRecord],
    *,
    embedding_model: str,
    embedding_dimensions: int,
    chunk_stats: dict[str, Any],
) -> dict[str, Any]:
    """Build scheme metadata index from corpus and chunk timestamps."""
    last_updated_by_slug: dict[str, str] = {}
    for chunk in chunks:
        last_updated_by_slug[chunk.slug] = chunk.last_updated

    schemes = []
    for scheme in corpus["schemes"]:
        slug = scheme["slug"]
        schemes.append(
            {
                "slug": slug,
                "scheme_name": scheme["scheme_name"],
                "category": scheme.get("category", ""),
                "source_url": scheme["source_url"],
                "aliases": scheme.get("aliases", []),
                "last_fetched_at": last_updated_by_slug.get(slug, ""),
            }
        )

    return {
        "amc": corpus.get("amc"),
        "source": corpus.get("source"),
        "updated_at": _utc_now_iso(),
        "embedding_model": embedding_model,
        "embedding_dimensions": embedding_dimensions,
        "chunk_stats": chunk_stats,
        "schemes": schemes,
    }


def _resolve_index_settings(
    settings: Settings,
    chunks: list[ChunkRecord],
) -> tuple[Settings, dict[str, Any]]:
    stats = compute_chunk_stats(chunks)
    model_name = resolve_embedding_model(
        explicit_model=settings.embedding_model,
        preset=settings.embedding_preset,
        stats=stats,
    )
    spec = get_model_spec(model_name)
    index_settings = replace(settings, embedding_model=model_name)
    chunk_stats = {
        "count": stats.count,
        "max_tokens": stats.max_tokens,
        "avg_tokens": round(stats.avg_tokens, 1),
        "preset": settings.embedding_preset,
    }
    logger.info(
        "Embedding model: %s (%s-dim) for %s chunks (avg %.1f tokens, max %s)",
        model_name,
        spec.dimensions,
        stats.count,
        stats.avg_tokens,
        stats.max_tokens,
    )
    return index_settings, chunk_stats


def _chunk_to_index_row(chunk: ChunkRecord, vector: list[float]) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "slug": chunk.slug,
        "scheme_name": chunk.scheme_name,
        "source_url": chunk.source_url,
        "section": chunk.section,
        "text": chunk.text,
        "last_updated": chunk.last_updated,
        "chunk_index": chunk.chunk_index,
        "vector": vector,
    }


def write_lance_table(
    chunks: list[ChunkRecord],
    db_path: Path,
    settings: Settings,
) -> int:
    """Embed chunks and write LanceDB table. Returns row count."""
    if not chunks:
        raise ValueError("Cannot index zero chunks")

    if db_path.exists():
        shutil.rmtree(db_path)
    db_path.mkdir(parents=True, exist_ok=True)

    texts = [chunk.text for chunk in chunks]
    vectors = embed_documents(texts, settings)
    rows = [_chunk_to_index_row(chunk, vector) for chunk, vector in zip(chunks, vectors)]

    db = lancedb.connect(db_path)
    db.create_table(CHUNKS_TABLE_NAME, rows, mode="overwrite")
    logger.info("Indexed %s chunks into LanceDB at %s", len(rows), db_path)
    return len(rows)


def write_scheme_metadata(metadata: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote scheme metadata -> %s", path)


def _atomic_replace_dir(staging_path: Path, live_path: Path) -> None:
    backup_path = live_path.parent / f"{live_path.name}.bak"
    if backup_path.exists():
        shutil.rmtree(backup_path)
    if live_path.exists():
        live_path.rename(backup_path)
    try:
        staging_path.rename(live_path)
        if backup_path.exists():
            shutil.rmtree(backup_path)
    except Exception:
        if backup_path.exists() and not live_path.exists():
            backup_path.rename(live_path)
        raise


def index_all(
    settings: Settings | None = None,
    *,
    chunks: list[ChunkRecord] | None = None,
    use_staging: bool = True,
) -> dict[str, Any]:
    """
    Embed all chunks, write LanceDB + scheme_metadata.json.
    Uses staging directory and atomic swap when use_staging=True.
    """
    settings = settings or get_settings()
    corpus = load_corpus(settings.corpus_path)
    chunk_records = chunks or load_chunk_records(settings)

    if not chunk_records:
        raise ValueError("No chunks found. Run ingestion.chunk first.")

    index_settings, chunk_stats = _resolve_index_settings(settings, chunk_records)
    spec = get_model_spec(index_settings.embedding_model)
    metadata = build_scheme_metadata(
        corpus,
        chunk_records,
        embedding_model=index_settings.embedding_model,
        embedding_dimensions=spec.dimensions,
        chunk_stats=chunk_stats,
    )

    if use_staging:
        staging_root = settings.index_staging_dir
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_db = staging_root / "lancedb"
        staging_meta = staging_root / "scheme_metadata.json"

        row_count = write_lance_table(chunk_records, staging_db, index_settings)
        write_scheme_metadata(metadata, staging_meta)

        _atomic_replace_dir(staging_db, settings.lance_db_uri)
        shutil.copy2(staging_meta, settings.scheme_metadata_path)
        shutil.rmtree(staging_root)
    else:
        row_count = write_lance_table(chunk_records, settings.lance_db_uri, index_settings)
        write_scheme_metadata(metadata, settings.scheme_metadata_path)

    summary = {
        "chunk_count": row_count,
        "scheme_count": len(metadata["schemes"]),
        "embedding_model": index_settings.embedding_model,
        "embedding_dimensions": spec.dimensions,
        "lance_db_uri": str(settings.lance_db_uri),
        "scheme_metadata_path": str(settings.scheme_metadata_path),
    }
    logger.info("Index complete: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = index_all()
    print(f"Indexed {result['chunk_count']} chunks for " f"{result['scheme_count']} schemes")
