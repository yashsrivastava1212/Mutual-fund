"""Tests for ingestion.parse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import get_settings
from ingestion.parse import (
    build_sections_from_mf_data,
    clean_html_to_text,
    extract_mf_server_side_data,
    parse_all,
    parse_html,
    parse_scheme_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MID_CAP_FIXTURE = FIXTURES_DIR / "hdfc-mid-cap-fund-direct-growth.html"


@pytest.fixture(scope="module")
def mid_cap_html() -> str:
    if not MID_CAP_FIXTURE.exists():
        pytest.skip("fixture HTML not available")
    return MID_CAP_FIXTURE.read_text(encoding="utf-8")


def test_extract_mf_server_side_data(mid_cap_html: str) -> None:
    mf = extract_mf_server_side_data(mid_cap_html)
    assert mf is not None
    assert mf["search_id"] == "hdfc-mid-cap-fund-direct-growth"
    assert float(mf["expense_ratio"]) == 0.73


def test_build_sections_includes_fund_management(mid_cap_html: str) -> None:
    mf = extract_mf_server_side_data(mid_cap_html)
    assert mf is not None
    sections = build_sections_from_mf_data(mf)
    section_names = {s.section for s in sections}

    assert "expense_ratio" in section_names
    assert "exit_load" in section_names
    assert "fund_management" in section_names
    assert "benchmark" in section_names
    assert "minimum_sip" in section_names
    assert "riskometer" in section_names

    fm = next(s for s in sections if s.section == "fund_management")
    assert "Chirag Setalvad" in fm.text
    assert len(fm.facts["managers"]) >= 1


def test_parse_html_produces_expected_sections(mid_cap_html: str) -> None:
    scheme = {
        "slug": "hdfc-mid-cap-fund-direct-growth",
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "category": "Equity — Mid Cap",
    }
    parsed = parse_html(mid_cap_html, scheme, fetched_at="2026-06-09")
    assert parsed.slug == scheme["slug"]
    assert parsed.scheme_name == "HDFC Mid Cap Fund Direct Growth"
    assert len(parsed.sections) >= 6

    expense = next(s for s in parsed.sections if s.section == "expense_ratio")
    assert "0.73" in expense.text


def test_clean_html_to_text_strips_scripts() -> None:
    html = "<html><head><script>bad()</script></head><body><p>Expense ratio 1%</p></body></html>"
    text = clean_html_to_text(html)
    assert "bad()" not in text
    assert "Expense ratio 1%" in text


def test_parse_scheme_file_writes_processed_json(
    tmp_path: Path, mid_cap_html: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    settings = get_settings()
    slug = "hdfc-mid-cap-fund-direct-growth"
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()

    (raw_dir / f"{slug}.html").write_text(mid_cap_html, encoding="utf-8")
    (raw_dir / f"{slug}.meta.json").write_text(
        json.dumps({"fetched_at": "2026-06-09"}),
        encoding="utf-8",
    )

    scheme = {
        "slug": slug,
        "scheme_name": "HDFC Mid Cap Fund Direct Growth",
        "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "category": "Equity — Mid Cap",
    }

    test_settings = replace(settings, data_raw_dir=raw_dir, data_processed_dir=processed_dir)
    monkeypatch.setattr("ingestion.parse.get_settings", lambda: test_settings)
    parsed = parse_scheme_file(scheme, test_settings)

    assert parsed is not None
    out = processed_dir / f"{slug}.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["last_updated"] == "2026-06-09"
    assert any(s["section"] == "fund_management" for s in data["sections"])


def test_parse_all_skips_missing_raw_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace

    settings = get_settings()
    test_settings = replace(
        settings,
        data_raw_dir=tmp_path / "empty_raw",
        data_processed_dir=tmp_path / "processed",
    )
    monkeypatch.setattr("ingestion.parse.get_settings", lambda: test_settings)
    results = parse_all(settings=test_settings)
    assert results == []
