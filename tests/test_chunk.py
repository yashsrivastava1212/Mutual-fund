"""Tests for ingestion.chunk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import get_settings
from ingestion.chunk import (
    FUND_MANAGEMENT_SECTION,
    chunk_all,
    chunk_parsed_scheme,
    chunk_section,
)

FIXTURE_PARSED = Path(__file__).parent / "fixtures" / "parsed-mid-cap.json"


@pytest.fixture
def mid_cap_parsed() -> dict:
    if FIXTURE_PARSED.exists():
        return json.loads(FIXTURE_PARSED.read_text(encoding="utf-8"))
    # Build minimal parsed object from processed file if fixture missing
    processed = (
        Path(__file__).parent.parent / "data" / "processed" / "hdfc-mid-cap-fund-direct-growth.json"
    )
    if processed.exists():
        return json.loads(processed.read_text(encoding="utf-8"))
    pytest.skip("parsed fixture not available")


def test_chunk_section_skips_empty_lock_in() -> None:
    chunks = chunk_section(
        slug="test",
        scheme_name="Test Fund",
        source_url="https://groww.in/mutual-funds/test",
        last_updated="2026-06-09",
        section="lock_in",
        text="Lock-in period: {'years': None}",
        facts={"lock_in": {"years": None, "months": None, "days": None}},
    )
    assert chunks == []


def test_chunk_section_one_per_factual_section() -> None:
    chunks = chunk_section(
        slug="hdfc-mid-cap-fund-direct-growth",
        scheme_name="HDFC Mid Cap Fund Direct Growth",
        source_url="https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        last_updated="2026-06-09",
        section="expense_ratio",
        text="The expense ratio of HDFC Mid Cap Fund Direct Growth is 0.73%.",
        facts={"expense_ratio": 0.73},
    )
    assert len(chunks) == 1
    assert chunks[0].section == "expense_ratio"
    assert "Section: expense_ratio" in chunks[0].text
    assert "0.73%" in chunks[0].text


def test_chunk_section_splits_fund_management_per_manager(mid_cap_parsed: dict) -> None:
    fm = next(s for s in mid_cap_parsed["sections"] if s["section"] == FUND_MANAGEMENT_SECTION)
    chunks = chunk_section(
        slug=mid_cap_parsed["slug"],
        scheme_name=mid_cap_parsed["scheme_name"],
        source_url=mid_cap_parsed["source_url"],
        last_updated=mid_cap_parsed["last_updated"],
        section=fm["section"],
        text=fm["text"],
        facts=fm["facts"],
    )
    manager_count = len(fm["facts"]["managers"])
    assert len(chunks) == manager_count
    assert all(c.section == FUND_MANAGEMENT_SECTION for c in chunks)
    assert chunks[0].id.endswith("#0")
    assert "Fund Manager" in chunks[0].text


def test_chunk_parsed_scheme_skips_lock_in(mid_cap_parsed: dict) -> None:
    chunks = chunk_parsed_scheme(mid_cap_parsed)
    sections = {c.section for c in chunks}
    assert "lock_in" not in sections
    assert "expense_ratio" in sections
    assert "fund_management" in sections


def test_chunk_all_writes_chunk_files(tmp_path: Path, mid_cap_parsed: dict) -> None:
    from dataclasses import replace

    settings = get_settings()
    processed_dir = tmp_path / "processed"
    chunks_dir = tmp_path / "chunks"
    processed_dir.mkdir()
    chunks_dir.mkdir()

    parsed_path = processed_dir / "hdfc-mid-cap-fund-direct-growth.json"
    parsed_path.write_text(json.dumps(mid_cap_parsed), encoding="utf-8")

    test_settings = replace(
        settings,
        data_processed_dir=processed_dir,
        data_chunks_dir=chunks_dir,
    )
    results = chunk_all(settings=test_settings, parsed_dir=processed_dir)

    assert len(results) >= 9
    out = chunks_dir / "hdfc-mid-cap-fund-direct-growth.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["chunk_count"] == len(results)
