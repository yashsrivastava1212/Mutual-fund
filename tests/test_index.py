"""Tests for ingestion.index."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import lancedb
import pytest

from config.embedding_models import BGE_SMALL, get_model_spec
from config.settings import get_settings
from ingestion.chunk import chunk_parsed_scheme
from ingestion.index import (
    build_scheme_metadata,
    index_all,
    load_chunk_records,
    write_lance_table,
)
from ingestion.schemas import ChunkRecord


def _fake_vectors(texts: list[str], settings=None) -> list[list[float]]:
    dim = get_model_spec((settings or get_settings()).embedding_model).dimensions
    return [[0.1] * dim for _ in texts]


@pytest.fixture
def sample_chunks(mid_cap_parsed_from_processed) -> list[ChunkRecord]:
    return chunk_parsed_scheme(mid_cap_parsed_from_processed)


@pytest.fixture
def mid_cap_parsed_from_processed() -> dict:
    path = (
        Path(__file__).parent.parent / "data" / "processed" / "hdfc-mid-cap-fund-direct-growth.json"
    )
    if not path.exists():
        pytest.skip("processed data not available")
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_scheme_metadata(sample_chunks: list[ChunkRecord]) -> None:
    from config.settings import load_corpus

    corpus = load_corpus()
    metadata = build_scheme_metadata(
        corpus,
        sample_chunks,
        embedding_model=BGE_SMALL,
        embedding_dimensions=384,
        chunk_stats={"count": len(sample_chunks), "max_tokens": 65, "avg_tokens": 30},
    )
    assert len(metadata["schemes"]) == 5
    mid_cap = next(s for s in metadata["schemes"] if s["slug"] == "hdfc-mid-cap-fund-direct-growth")
    assert mid_cap["last_fetched_at"] == sample_chunks[0].last_updated


def test_write_lance_table(tmp_path: Path, sample_chunks: list[ChunkRecord]) -> None:
    from dataclasses import replace

    settings = replace(get_settings(), embedding_model="sentence-transformers/all-MiniLM-L6-v2")
    db_path = tmp_path / "lancedb"

    with patch("ingestion.index.embed_documents", side_effect=_fake_vectors):
        count = write_lance_table(sample_chunks, db_path, settings)

    assert count == len(sample_chunks)
    db = lancedb.connect(db_path)
    table = db.open_table("chunks")
    rows = table.to_arrow().to_pylist()
    assert len(rows) == len(sample_chunks)
    assert rows[0]["vector"] is not None


def test_index_all_with_staging(tmp_path: Path, sample_chunks: list[ChunkRecord]) -> None:
    from dataclasses import replace

    settings = get_settings()
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    index_dir = tmp_path / "index"
    staging_dir = index_dir / "staging"

    payload = {
        "slug": "hdfc-mid-cap-fund-direct-growth",
        "chunks": [
            {
                "id": c.id,
                "slug": c.slug,
                "scheme_name": c.scheme_name,
                "source_url": c.source_url,
                "section": c.section,
                "text": c.text,
                "last_updated": c.last_updated,
                "chunk_index": c.chunk_index,
            }
            for c in sample_chunks
        ],
    }
    (chunks_dir / "hdfc-mid-cap-fund-direct-growth.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    test_settings = replace(
        settings,
        data_chunks_dir=chunks_dir,
        data_index_dir=index_dir,
        lance_db_uri=index_dir / "lancedb",
        scheme_metadata_path=index_dir / "scheme_metadata.json",
        index_staging_dir=staging_dir,
    )

    with patch("ingestion.index.embed_documents", side_effect=_fake_vectors):
        result = index_all(test_settings, chunks=sample_chunks)

    assert result["chunk_count"] == len(sample_chunks)
    assert (index_dir / "lancedb").exists()
    assert (index_dir / "scheme_metadata.json").exists()
    meta = json.loads((index_dir / "scheme_metadata.json").read_text(encoding="utf-8"))
    assert len(meta["schemes"]) == 5


def test_load_chunk_records_reads_chunks_dir(
    tmp_path: Path, sample_chunks: list[ChunkRecord]
) -> None:
    from dataclasses import replace

    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    payload = {
        "chunks": [
            {
                "id": c.id,
                "slug": c.slug,
                "scheme_name": c.scheme_name,
                "source_url": c.source_url,
                "section": c.section,
                "text": c.text,
                "last_updated": c.last_updated,
                "chunk_index": c.chunk_index,
            }
            for c in sample_chunks
        ]
    }
    (chunks_dir / "test.json").write_text(json.dumps(payload), encoding="utf-8")

    settings = replace(get_settings(), data_chunks_dir=chunks_dir)
    loaded = load_chunk_records(settings)
    assert len(loaded) == len(sample_chunks)
