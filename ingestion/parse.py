"""Parse fetched Groww HTML into structured scheme sections."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from config.settings import Settings, get_settings, load_corpus
from ingestion.schemas import ParsedScheme, SectionBlock

logger = logging.getLogger(__name__)

CHROME_TAGS = {"script", "style", "noscript", "svg", "header", "footer", "nav"}
CHROME_SELECTORS = [
    "[class*='header']",
    "[class*='footer']",
    "[class*='navbar']",
    "[class*='dropdown']",
    "[class*='cookie']",
]


def extract_mf_server_side_data(html: str) -> dict[str, Any] | None:
    """Extract Groww mfServerSideData from __NEXT_DATA__ script tag."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        payload = json.loads(script.string)
        return payload["props"]["pageProps"]["mfServerSideData"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Could not parse __NEXT_DATA__: %s", exc)
        return None


def _format_date_from_iso(value: str | None) -> str:
    if not value:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%b %Y")
    except ValueError:
        return value


def _build_fund_management_section(managers: list[dict[str, Any]]) -> SectionBlock:
    lines: list[str] = []
    manager_facts: list[dict[str, Any]] = []

    for manager in managers:
        name = manager.get("person_name") or "Unknown"
        since = _format_date_from_iso(manager.get("date_from"))
        education = (manager.get("education") or "").strip()
        experience = (manager.get("experience") or "").strip()

        lines.append(f"{name} — Fund Manager, since {since}.")
        if education:
            lines.append(f"Education: {education}")
        if experience:
            lines.append(f"Experience: {experience}")
        lines.append("")

        manager_facts.append(
            {
                "person_name": name,
                "date_from": manager.get("date_from"),
                "education": education,
                "experience": experience,
            }
        )

    text = "\n".join(line for line in lines if line).strip()
    return SectionBlock(
        section="fund_management",
        text=text,
        facts={"managers": manager_facts},
    )


def _section_from_facts(section: str, lines: list[str], facts: dict[str, Any]) -> SectionBlock:
    return SectionBlock(section=section, text="\n".join(lines), facts=facts)


def build_sections_from_mf_data(mf: dict[str, Any]) -> list[SectionBlock]:
    """Map mfServerSideData fields to logical FAQ sections."""
    sections: list[SectionBlock] = []

    scheme_name = mf.get("scheme_name") or "Unknown scheme"
    category = mf.get("category") or ""
    sub_category = mf.get("sub_category") or ""
    description = (mf.get("description") or "").strip()
    launch_date = mf.get("launch_date") or ""
    amc = mf.get("fund_house") or mf.get("amc") or ""

    overview_lines = [
        f"Scheme: {scheme_name}",
        f"AMC: {amc}",
        f"Category: {category}" + (f" — {sub_category}" if sub_category else ""),
    ]
    if launch_date:
        overview_lines.append(f"Launch date: {launch_date}")
    if description:
        overview_lines.append(f"Investment objective: {description}")

    sections.append(
        _section_from_facts(
            "scheme_overview",
            overview_lines,
            {
                "scheme_name": scheme_name,
                "category": category,
                "sub_category": sub_category,
                "launch_date": launch_date,
                "description": description,
            },
        )
    )

    expense_ratio_raw = mf.get("expense_ratio")
    expense_ratio: float | str | None = expense_ratio_raw
    if expense_ratio_raw is not None:
        try:
            expense_ratio = float(expense_ratio_raw)
        except (TypeError, ValueError):
            expense_ratio = str(expense_ratio_raw)
        sections.append(
            _section_from_facts(
                "expense_ratio",
                [f"The expense ratio of {scheme_name} is {expense_ratio}%."],
                {"expense_ratio": expense_ratio},
            )
        )

    exit_load = (mf.get("exit_load") or "").strip()
    if exit_load:
        sections.append(
            _section_from_facts(
                "exit_load",
                [f"Exit load: {exit_load}"],
                {"exit_load": exit_load, "historic_exit_loads": mf.get("historic_exit_loads")},
            )
        )

    min_sip = mf.get("min_sip_investment")
    if min_sip is not None:
        sections.append(
            _section_from_facts(
                "minimum_sip",
                [f"Minimum SIP investment for {scheme_name} is ₹{min_sip}."],
                {
                    "min_sip_investment": min_sip,
                    "sip_allowed": mf.get("sip_allowed"),
                    "max_sip_investment": mf.get("max_sip_investment"),
                },
            )
        )

    min_lumpsum = mf.get("min_investment_amount")
    if min_lumpsum is not None:
        sections.append(
            _section_from_facts(
                "minimum_investment",
                [f"Minimum lumpsum investment for {scheme_name} is ₹{min_lumpsum}."],
                {"min_investment_amount": min_lumpsum},
            )
        )

    risk = (mf.get("nfo_risk") or "").strip()
    if risk:
        sections.append(
            _section_from_facts(
                "riskometer",
                [f"Risk level for {scheme_name}: {risk}."],
                {"risk": risk},
            )
        )

    benchmark = (mf.get("benchmark_name") or mf.get("benchmark") or "").strip()
    if benchmark:
        sections.append(
            _section_from_facts(
                "benchmark",
                [f"Fund benchmark for {scheme_name}: {benchmark}."],
                {
                    "benchmark": mf.get("benchmark"),
                    "benchmark_name": mf.get("benchmark_name"),
                },
            )
        )

    lock_in = mf.get("lock_in")
    if lock_in:
        sections.append(
            _section_from_facts(
                "lock_in",
                [f"Lock-in period: {lock_in}."],
                {"lock_in": lock_in},
            )
        )

    stamp_duty = mf.get("stamp_duty")
    if stamp_duty is not None:
        sections.append(
            _section_from_facts(
                "stamp_duty",
                [f"Stamp duty: {stamp_duty}."],
                {"stamp_duty": stamp_duty},
            )
        )

    managers = mf.get("fund_manager_details") or []
    if managers:
        sections.append(_build_fund_management_section(managers))
    elif mf.get("fund_manager"):
        sections.append(
            _section_from_facts(
                "fund_management",
                [f"Fund manager: {mf['fund_manager']}."],
                {"fund_manager": mf["fund_manager"]},
            )
        )

    return sections


def clean_html_to_text(html: str) -> str:
    """Fallback: strip chrome and return condensed visible text."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(CHROME_TAGS):
        tag.decompose()

    for selector in CHROME_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    text = soup.get_text(separator="\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line and len(line) > 2]
    return "\n".join(lines)


def parse_html(
    html: str,
    scheme: dict[str, Any],
    *,
    fetched_at: str,
) -> ParsedScheme:
    """Parse one scheme HTML into structured sections."""
    slug = scheme["slug"]
    mf = extract_mf_server_side_data(html)
    sections: list[SectionBlock] = []

    if mf:
        sections = build_sections_from_mf_data(mf)
        scheme_name = mf.get("scheme_name") or scheme["scheme_name"]
        category = mf.get("category") or scheme.get("category", "")
    else:
        logger.warning("mfServerSideData missing for %s; using HTML text fallback", slug)
        scheme_name = scheme["scheme_name"]
        category = scheme.get("category", "")
        fallback_text = clean_html_to_text(html)
        if fallback_text:
            sections.append(
                SectionBlock(
                    section="raw_content",
                    text=fallback_text[:8000],
                    facts={"source": "html_fallback"},
                )
            )

    return ParsedScheme(
        slug=slug,
        scheme_name=scheme_name,
        source_url=scheme["source_url"],
        category=category,
        last_updated=fetched_at,
        sections=sections,
    )


def _parsed_scheme_to_dict(parsed: ParsedScheme) -> dict[str, Any]:
    return {
        "slug": parsed.slug,
        "scheme_name": parsed.scheme_name,
        "source_url": parsed.source_url,
        "category": parsed.category,
        "last_updated": parsed.last_updated,
        "sections": [
            {"section": s.section, "text": s.text, "facts": s.facts} for s in parsed.sections
        ],
    }


def parse_scheme_file(
    scheme: dict[str, Any],
    settings: Settings,
    *,
    html_path: Path | None = None,
) -> ParsedScheme | None:
    """Parse a scheme from its saved raw HTML file."""
    raw_dir = settings.data_raw_dir
    processed_dir = settings.data_processed_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    slug = scheme["slug"]
    html_file = html_path or raw_dir / f"{slug}.html"
    meta_file = raw_dir / f"{slug}.meta.json"

    if not html_file.exists():
        logger.error("Raw HTML not found for %s: %s", slug, html_file)
        return None

    fetched_at = scheme.get("last_fetched_at") or ""
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            fetched_at = meta.get("fetched_at") or fetched_at
        except json.JSONDecodeError:
            pass
    if not fetched_at:
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    html = html_file.read_text(encoding="utf-8")
    parsed = parse_html(html, scheme, fetched_at=fetched_at)

    output_path = processed_dir / f"{slug}.json"
    output_path.write_text(
        json.dumps(_parsed_scheme_to_dict(parsed), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    parsed.output_path = output_path
    logger.info(
        "Parsed %s: %s sections -> %s",
        slug,
        len(parsed.sections),
        output_path,
    )
    return parsed


def parse_all(
    settings: Settings | None = None,
    *,
    schemes: list[dict[str, Any]] | None = None,
) -> list[ParsedScheme]:
    """Parse all schemes that have raw HTML in data/raw."""
    settings = settings or get_settings()
    corpus = load_corpus(settings.corpus_path)
    scheme_list = schemes or corpus["schemes"]
    parsed_schemes: list[ParsedScheme] = []

    for scheme in scheme_list:
        result = parse_scheme_file(scheme, settings)
        if result:
            parsed_schemes.append(result)

    logger.info("Parse complete: %s/%s schemes", len(parsed_schemes), len(scheme_list))
    return parsed_schemes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = parse_all()
    if not results:
        raise SystemExit("No schemes parsed. Run ingestion.fetch first.")
    print(f"Parsed {len(results)} schemes into {get_settings().data_processed_dir}")
