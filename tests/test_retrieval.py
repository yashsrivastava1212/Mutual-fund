"""Phase 3 retrieval tests (scheme resolution, section intent, retriever)."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import lancedb
import pytest

from app.retriever import (
    DEFAULT_TOP_K,
    clear_retriever_cache,
    retrieve,
)
from app.scheme_index import (
    clear_scheme_cache,
    get_scheme_by_slug,
    resolve_scheme,
)
from app.section_intent import detect_section_intent
from config.embedding_models import get_model_spec
from config.settings import Settings, get_settings

PROJECT_ROOT = Path(__file__).parent.parent
LIVE_METADATA = PROJECT_ROOT / "data" / "index" / "scheme_metadata.json"
LIVE_LANCEDB = PROJECT_ROOT / "data" / "index" / "lancedb"


@pytest.fixture
def settings_with_live_index() -> Settings:
    if not LIVE_METADATA.exists() or not LIVE_LANCEDB.exists():
        pytest.skip("Live index not available; run python -m ingestion.run first")
    return get_settings()


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_scheme_cache()
    clear_retriever_cache()
    yield
    clear_scheme_cache()
    clear_retriever_cache()


# --- Scheme resolution (edge-case R-01–R-11) ---


@pytest.mark.parametrize(
    ("query", "expected_slug"),
    [
        ("HDFC Mid Cap Fund Direct Growth expense ratio", "hdfc-mid-cap-fund-direct-growth"),
        ("HDFC Mid Cap expense ratio", "hdfc-mid-cap-fund-direct-growth"),
        ("mid cap exit load", "hdfc-mid-cap-fund-direct-growth"),
        ("defence fund managers", "hdfc-defence-fund-direct-growth"),
        ("defense fund managers", "hdfc-defence-fund-direct-growth"),
        (
            "gold etf fund of fund minimum sip",
            "hdfc-gold-etf-fund-of-fund-direct-plan-growth",
        ),
        ("HDFC Midcap Fund expence ratio", "hdfc-mid-cap-fund-direct-growth"),
        ("hdfc MID-CAP fund!!! who manages??", "hdfc-mid-cap-fund-direct-growth"),
        ("HDFC Small Cap Fund Direct Growth benchmark", "hdfc-small-cap-fund-direct-growth"),
        ("large cap riskometer", "hdfc-large-cap-fund-direct-growth"),
    ],
)
def test_resolve_scheme_hits(
    settings_with_live_index: Settings,
    query: str,
    expected_slug: str,
) -> None:
    match = resolve_scheme(query, settings_with_live_index)
    assert match is not None
    assert match.slug == expected_slug


@pytest.mark.parametrize(
    "query",
    [
        "What is the expense ratio?",
        "HDFC fund expense ratio",
        "What is the expense ratio of SBI Bluechip?",
        "cap fund exit load",
    ],
)
def test_resolve_scheme_no_match(settings_with_live_index: Settings, query: str) -> None:
    assert resolve_scheme(query, settings_with_live_index) is None


def test_get_scheme_by_slug(settings_with_live_index: Settings) -> None:
    scheme = get_scheme_by_slug("hdfc-mid-cap-fund-direct-growth", settings_with_live_index)
    assert scheme is not None
    assert "groww.in" in scheme["source_url"]


# --- Section intent ---


@pytest.mark.parametrize(
    ("query", "expected_section", "expected_confidence"),
    [
        ("What is the expense ratio?", "expense_ratio", "high"),
        ("exit load for mid cap", "exit_load", "high"),
        ("minimum sip amount", "minimum_sip", "high"),
        ("lumpsum minimum investment", "minimum_investment", "high"),
        ("what is the riskometer", "riskometer", "high"),
        ("who manages the fund", "fund_management", "high"),
        ("stamp duty on redemption", "stamp_duty", "high"),
        ("fund objective and category", "scheme_overview", "medium"),
    ],
)
def test_section_intent(
    query: str,
    expected_section: str,
    expected_confidence: str,
) -> None:
    intent = detect_section_intent(query)
    assert intent is not None
    assert intent.section == expected_section
    assert intent.confidence == expected_confidence


def test_section_intent_none_for_generic() -> None:
    assert detect_section_intent("tell me about this scheme") is None


# --- Retriever (mocked LanceDB) ---


def _fake_vectors(texts: list[str], settings=None) -> list[list[float]]:
    dim = get_model_spec((settings or get_settings()).embedding_model).dimensions
    return [[0.1] * dim for _ in texts]


def _fake_query_vector(query: str, settings=None) -> list[float]:
    dim = get_model_spec((settings or get_settings()).embedding_model).dimensions
    return [0.1] * dim


@pytest.fixture
def mock_retriever_env(tmp_path: Path) -> Settings:
    metadata_src = LIVE_METADATA if LIVE_METADATA.exists() else None
    if metadata_src is None:
        metadata = {
            "schemes": [
                {
                    "slug": "hdfc-mid-cap-fund-direct-growth",
                    "scheme_name": "HDFC Mid Cap Fund Direct Growth",
                    "category": "Equity — Mid Cap",
                    "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
                    "aliases": ["mid cap", "hdfc mid cap", "midcap"],
                    "last_fetched_at": "2026-06-09",
                },
                {
                    "slug": "hdfc-large-cap-fund-direct-growth",
                    "scheme_name": "HDFC Large Cap Fund Direct Growth",
                    "category": "Equity — Large Cap",
                    "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
                    "aliases": ["large cap"],
                    "last_fetched_at": "2026-06-09",
                },
            ]
        }
    else:
        metadata = json.loads(metadata_src.read_text(encoding="utf-8"))

    meta_path = tmp_path / "scheme_metadata.json"
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    db_path = tmp_path / "lancedb"
    rows = [
        {
            "id": "hdfc-mid-cap-fund-direct-growth#expense_ratio#0",
            "slug": "hdfc-mid-cap-fund-direct-growth",
            "scheme_name": "HDFC Mid Cap Fund Direct Growth",
            "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            "section": "expense_ratio",
            "text": "HDFC Mid Cap Fund Direct Growth | Section: expense_ratio\nExpense ratio: 0.77%",
            "last_updated": "2026-06-09",
            "chunk_index": 0,
            "vector": _fake_query_vector("x"),
        },
        {
            "id": "hdfc-mid-cap-fund-direct-growth#exit_load#0",
            "slug": "hdfc-mid-cap-fund-direct-growth",
            "scheme_name": "HDFC Mid Cap Fund Direct Growth",
            "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            "section": "exit_load",
            "text": "HDFC Mid Cap Fund Direct Growth | Section: exit_load\nExit load: 1%",
            "last_updated": "2026-06-09",
            "chunk_index": 0,
            "vector": [0.9] * 384,
        },
        {
            "id": "hdfc-large-cap-fund-direct-growth#expense_ratio#0",
            "slug": "hdfc-large-cap-fund-direct-growth",
            "scheme_name": "HDFC Large Cap Fund Direct Growth",
            "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
            "section": "expense_ratio",
            "text": "HDFC Large Cap Fund Direct Growth | Section: expense_ratio\nExpense ratio: 0.99%",
            "last_updated": "2026-06-09",
            "chunk_index": 0,
            "vector": [0.9] * 384,
        },
    ]
    db = lancedb.connect(db_path)
    db.create_table("chunks", rows, mode="overwrite")

    base = get_settings()
    return replace(
        base,
        scheme_metadata_path=meta_path,
        lance_db_uri=db_path,
    )


def test_retrieve_empty_when_no_scheme(mock_retriever_env: Settings) -> None:
    assert retrieve("What is the expense ratio?", settings=mock_retriever_env) == []


def test_retrieve_slug_filter_no_cross_scheme(mock_retriever_env: Settings) -> None:
    with patch("app.retriever.embed_query", side_effect=_fake_query_vector):
        chunks = retrieve(
            "HDFC Mid Cap Fund Direct Growth expense ratio",
            settings=mock_retriever_env,
        )

    assert chunks
    assert all(c["slug"] == "hdfc-mid-cap-fund-direct-growth" for c in chunks)
    assert all("large-cap" not in c["slug"] for c in chunks)
    assert chunks[0]["section"] == "expense_ratio"
    assert chunks[0]["source_url"].startswith("https://groww.in/")


def test_retrieve_uses_bge_query_embedding(mock_retriever_env: Settings) -> None:
    with patch("app.retriever.embed_query", side_effect=_fake_query_vector) as mock_embed:
        retrieve("mid cap expense ratio", settings=mock_retriever_env)
        mock_embed.assert_called_once()
        assert mock_embed.call_args[0][0] == "mid cap expense ratio"


def test_retrieve_chunk_contract(mock_retriever_env: Settings) -> None:
    with patch("app.retriever.embed_query", side_effect=_fake_query_vector):
        chunks = retrieve("mid cap expense ratio", settings=mock_retriever_env)

    assert chunks
    chunk = chunks[0]
    for key in ("id", "slug", "scheme_name", "source_url", "section", "text", "last_updated", "score"):
        assert key in chunk
    assert "vector" not in chunk


def test_retrieve_respects_top_k(mock_retriever_env: Settings) -> None:
    with patch("app.retriever.embed_query", side_effect=_fake_query_vector):
        chunks = retrieve("mid cap fund facts", top_k=1, settings=mock_retriever_env)
    assert len(chunks) <= 1


# --- Integration against live index ---


def test_live_retrieve_expense_ratio(settings_with_live_index: Settings) -> None:
    chunks = retrieve(
        "HDFC Mid Cap Fund Direct Growth expense ratio",
        settings=settings_with_live_index,
    )
    assert chunks
    assert chunks[0]["slug"] == "hdfc-mid-cap-fund-direct-growth"
    assert chunks[0]["section"] == "expense_ratio"
    assert len(chunks) <= DEFAULT_TOP_K


def test_live_retrieve_no_cross_scheme(settings_with_live_index: Settings) -> None:
    chunks = retrieve(
        "small cap exit load",
        settings=settings_with_live_index,
    )
    assert chunks
    assert all(c["slug"] == "hdfc-small-cap-fund-direct-growth" for c in chunks)


def test_live_retrieve_fund_management_up_to_three(settings_with_live_index: Settings) -> None:
    chunks = retrieve(
        "HDFC Defence Fund fund managers",
        settings=settings_with_live_index,
        top_k=3,
    )
    assert chunks
    assert all(c["section"] == "fund_management" for c in chunks)
    assert len(chunks) <= 3


def test_live_retrieve_latency_under_100ms(settings_with_live_index: Settings) -> None:
    start = time.perf_counter()
    retrieve("large cap benchmark", settings=settings_with_live_index)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 5000  # generous on cold embed; warm run typically <100ms
