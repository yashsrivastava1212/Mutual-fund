"""Shared ingestion data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FetchRecord:
    slug: str
    source_url: str
    fetched_at: str
    status_code: int | None
    success: bool
    html_path: Path | None = None
    meta_path: Path | None = None
    error: str | None = None


@dataclass
class SectionBlock:
    section: str
    text: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedScheme:
    slug: str
    scheme_name: str
    source_url: str
    category: str
    last_updated: str
    sections: list[SectionBlock]
    output_path: Path | None = None


@dataclass
class ChunkRecord:
    id: str
    slug: str
    scheme_name: str
    source_url: str
    section: str
    text: str
    last_updated: str
    chunk_index: int = 0
