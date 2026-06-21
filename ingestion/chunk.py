"""Section-first chunking with per-manager split for fund_management."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from config.settings import Settings, get_settings, load_corpus
from ingestion.parse import _format_date_from_iso
from ingestion.schemas import ChunkRecord

logger = logging.getLogger(__name__)

MAX_SECTION_TOKENS = 400
OVERLAP_TOKENS = 50
SKIP_SECTIONS: set[str] = set()

FUND_MANAGEMENT_SECTION = "fund_management"


def _approx_token_count(text: str) -> int:
    return len(text.split())


def _should_skip_section(section: str, text: str, facts: dict[str, Any]) -> bool:
    if section in SKIP_SECTIONS:
        return True
    if not text.strip():
        return True
    if section == "lock_in":
        lock = facts.get("lock_in")
        if isinstance(lock, dict) and not any(lock.get(k) for k in ("years", "months", "days")):
            return True
    return False


def _build_context_prefix(scheme_name: str, section: str) -> str:
    return f"{scheme_name} | Section: {section}"


def _format_manager_text(manager: dict[str, Any]) -> str:
    name = manager.get("person_name") or "Unknown"
    since = _format_date_from_iso(manager.get("date_from"))
    education = (manager.get("education") or "").strip()
    experience = (manager.get("experience") or "").strip()

    lines = [f"{name} — Fund Manager, since {since}."]
    if education:
        lines.append(f"Education: {education}")
    if experience:
        lines.append(f"Experience: {experience}")
    return "\n".join(lines)


def _split_long_text(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    words = text.split()
    if len(words) <= max_tokens:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(end - overlap_tokens, start + 1)
    return chunks


def _make_chunk_text(scheme_name: str, section: str, body: str) -> str:
    prefix = _build_context_prefix(scheme_name, section)
    return f"{prefix}\n{body.strip()}"


def _chunk_id(slug: str, section: str, index: int) -> str:
    safe_section = re.sub(r"[^a-z0-9_]+", "_", section.lower())
    return f"{slug}#{safe_section}#{index}"


def chunk_section(
    slug: str,
    scheme_name: str,
    source_url: str,
    last_updated: str,
    section: str,
    text: str,
    facts: dict[str, Any],
) -> list[ChunkRecord]:
    """Convert one parsed section into one or more chunk records."""
    if _should_skip_section(section, text, facts):
        return []

    records: list[ChunkRecord] = []

    if section == FUND_MANAGEMENT_SECTION and facts.get("managers"):
        for index, manager in enumerate(facts["managers"]):
            body = _format_manager_text(manager)
            records.append(
                ChunkRecord(
                    id=_chunk_id(slug, section, index),
                    slug=slug,
                    scheme_name=scheme_name,
                    source_url=source_url,
                    section=section,
                    text=_make_chunk_text(scheme_name, section, body),
                    last_updated=last_updated,
                    chunk_index=index,
                )
            )
        return records

    bodies = _split_long_text(text, MAX_SECTION_TOKENS, OVERLAP_TOKENS)
    for index, body in enumerate(bodies):
        records.append(
            ChunkRecord(
                id=_chunk_id(slug, section, index),
                slug=slug,
                scheme_name=scheme_name,
                source_url=source_url,
                section=section,
                text=_make_chunk_text(scheme_name, section, body),
                last_updated=last_updated,
                chunk_index=index,
            )
        )
    return records


def chunk_parsed_scheme(data: dict[str, Any]) -> list[ChunkRecord]:
    """Build chunk records from a parsed scheme JSON object."""
    slug = data["slug"]
    scheme_name = data["scheme_name"]
    source_url = data["source_url"]
    last_updated = data["last_updated"]
    chunks: list[ChunkRecord] = []

    for section_block in data.get("sections", []):
        chunks.extend(
            chunk_section(
                slug=slug,
                scheme_name=scheme_name,
                source_url=source_url,
                last_updated=last_updated,
                section=section_block["section"],
                text=section_block.get("text", ""),
                facts=section_block.get("facts", {}),
            )
        )
    return chunks


def _chunk_record_to_dict(chunk: ChunkRecord) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "slug": chunk.slug,
        "scheme_name": chunk.scheme_name,
        "source_url": chunk.source_url,
        "section": chunk.section,
        "text": chunk.text,
        "last_updated": chunk.last_updated,
        "chunk_index": chunk.chunk_index,
    }


def chunk_scheme_file(
    parsed_path: Path,
    settings: Settings,
) -> list[ChunkRecord]:
    """Chunk one parsed scheme file and write chunks JSON."""
    data = json.loads(parsed_path.read_text(encoding="utf-8"))
    chunks = chunk_parsed_scheme(data)
    settings.data_chunks_dir.mkdir(parents=True, exist_ok=True)

    output_path = settings.data_chunks_dir / f"{data['slug']}.json"
    payload = {
        "slug": data["slug"],
        "scheme_name": data["scheme_name"],
        "source_url": data["source_url"],
        "last_updated": data["last_updated"],
        "chunk_count": len(chunks),
        "chunks": [_chunk_record_to_dict(c) for c in chunks],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Chunked %s: %s chunks -> %s", data["slug"], len(chunks), output_path)
    return chunks


def chunk_all(
    settings: Settings | None = None,
    *,
    parsed_dir: Path | None = None,
) -> list[ChunkRecord]:
    """Chunk all parsed scheme JSON files."""
    settings = settings or get_settings()
    source_dir = parsed_dir or settings.data_processed_dir
    all_chunks: list[ChunkRecord] = []

    for parsed_path in sorted(source_dir.glob("*.json")):
        if parsed_path.parent.name == "chunks":
            continue
        all_chunks.extend(chunk_scheme_file(parsed_path, settings))

    logger.info("Chunk complete: %s total chunks", len(all_chunks))
    return all_chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    corpus = load_corpus()
    results = chunk_all()
    if not results:
        raise SystemExit("No chunks produced. Run ingestion.parse first.")
    print(f"Chunked {len(corpus['schemes'])} schemes -> {len(results)} chunks")
