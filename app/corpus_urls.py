"""Corpus URL helpers for citation validation."""

from __future__ import annotations

from functools import lru_cache

from config.settings import load_corpus


@lru_cache
def get_corpus_source_urls() -> frozenset[str]:
    corpus = load_corpus()
    return frozenset(scheme["source_url"] for scheme in corpus["schemes"])


def clear_corpus_url_cache() -> None:
    get_corpus_source_urls.cache_clear()
