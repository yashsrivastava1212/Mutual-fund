"""Tests for BGE embedding model selection."""

from __future__ import annotations

from config.embedding_models import (
    BGE_LARGE,
    BGE_SMALL,
    ChunkStats,
    recommend_bge_model,
    resolve_embedding_model,
)


def test_recommend_bge_small_for_current_corpus_size() -> None:
    stats = ChunkStats(count=51, max_tokens=65, avg_tokens=30.4)
    assert recommend_bge_model(stats) == BGE_SMALL


def test_recommend_bge_large_for_large_corpus() -> None:
    stats = ChunkStats(count=600, max_tokens=100, avg_tokens=80)
    assert recommend_bge_model(stats) == BGE_LARGE


def test_recommend_bge_large_for_long_chunks() -> None:
    stats = ChunkStats(count=50, max_tokens=450, avg_tokens=200)
    assert recommend_bge_model(stats) == BGE_LARGE


def test_resolve_preset_small() -> None:
    assert (
        resolve_embedding_model(
            explicit_model="",
            preset="small",
            stats=ChunkStats(51, 65, 30),
        )
        == BGE_SMALL
    )


def test_resolve_preset_large() -> None:
    assert (
        resolve_embedding_model(
            explicit_model="",
            preset="large",
            stats=ChunkStats(51, 65, 30),
        )
        == BGE_LARGE
    )


def test_resolve_preset_auto_uses_stats() -> None:
    assert (
        resolve_embedding_model(
            explicit_model="",
            preset="auto",
            stats=ChunkStats(51, 65, 30),
        )
        == BGE_SMALL
    )
