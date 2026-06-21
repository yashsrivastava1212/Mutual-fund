"""Phase 1: configuration and corpus tests."""

from __future__ import annotations

from config.embedding_models import BGE_SMALL
from config.settings import get_settings, load_corpus


def test_corpus_has_five_schemes() -> None:
    corpus = load_corpus()
    assert len(corpus["schemes"]) == 5
    assert corpus["amc"] == "HDFC Mutual Fund"


def test_corpus_urls_are_groww() -> None:
    corpus = load_corpus()
    for scheme in corpus["schemes"]:
        url = scheme["source_url"]
        assert url.startswith("https://groww.in/mutual-funds/")
        assert "slug" in scheme
        assert "aliases" in scheme


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.embedding_model == BGE_SMALL
    assert settings.embedding_preset == "auto"
    assert settings.corpus_path.exists()
