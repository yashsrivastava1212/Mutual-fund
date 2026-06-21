"""Fetch Groww scheme pages from corpus URLs."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config.settings import Settings, get_settings, load_corpus
from ingestion.schemas import FetchRecord

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; MutualFundFAQBot/0.1; +https://groww.in/mutual-funds)"
)
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BASE_DELAY_SECONDS = 2.0
DEFAULT_RATE_LIMIT_SECONDS = 1.5
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _scheme_raw_paths(raw_dir: Path, slug: str) -> tuple[Path, Path]:
    return raw_dir / f"{slug}.html", raw_dir / f"{slug}.meta.json"


def fetch_url(
    url: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_base_delay_seconds: float = DEFAULT_RETRY_BASE_DELAY_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[int | None, str | None, str | None]:
    """Fetch a single URL with retries. Returns (status_code, html, error)."""
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    last_error: str | None = None

    with httpx.Client(follow_redirects=True, timeout=timeout_seconds) as client:
        for attempt in range(1, retry_count + 1):
            try:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.status_code, response.text, None
                last_error = f"HTTP {response.status_code}"
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response.status_code, None, last_error
            except httpx.HTTPError as exc:
                last_error = str(exc)

            if attempt < retry_count:
                delay = retry_base_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Fetch attempt %s/%s failed for %s: %s; retrying in %.1fs",
                    attempt,
                    retry_count,
                    url,
                    last_error,
                    delay,
                )
                time.sleep(delay)

    return None, None, last_error or "Unknown fetch error"


def fetch_scheme(
    scheme: dict[str, Any],
    settings: Settings,
    *,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_base_delay_seconds: float = DEFAULT_RETRY_BASE_DELAY_SECONDS,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    sleep_after: bool = False,
) -> FetchRecord:
    """Fetch one scheme page and persist raw HTML + metadata."""
    slug = scheme["slug"]
    source_url = scheme["source_url"]
    fetched_at = _utc_now_iso()
    raw_dir = settings.data_raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    html_path, meta_path = _scheme_raw_paths(raw_dir, slug)

    status_code, html, error = fetch_url(
        source_url,
        retry_count=retry_count,
        retry_base_delay_seconds=retry_base_delay_seconds,
    )

    record = FetchRecord(
        slug=slug,
        source_url=source_url,
        fetched_at=fetched_at,
        status_code=status_code,
        success=bool(html),
        error=error,
    )

    if html:
        html_path.write_text(html, encoding="utf-8")
        meta = {
            "slug": slug,
            "source_url": source_url,
            "scheme_name": scheme.get("scheme_name"),
            "fetched_at": fetched_at,
            "status_code": status_code,
            "content_length": len(html),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        record.html_path = html_path
        record.meta_path = meta_path
        logger.info("Fetched %s (%s bytes)", slug, len(html))
    else:
        logger.error("Failed to fetch %s: %s", slug, error)

    if sleep_after and rate_limit_seconds > 0:
        time.sleep(rate_limit_seconds)

    return record


def fetch_all(
    settings: Settings | None = None,
    *,
    schemes: list[dict[str, Any]] | None = None,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
) -> list[FetchRecord]:
    """Fetch all corpus scheme pages with rate limiting between requests."""
    settings = settings or get_settings()
    corpus = load_corpus(settings.corpus_path)
    scheme_list = schemes or corpus["schemes"]
    records: list[FetchRecord] = []

    for index, scheme in enumerate(scheme_list):
        record = fetch_scheme(
            scheme,
            settings,
            sleep_after=index < len(scheme_list) - 1,
            rate_limit_seconds=rate_limit_seconds,
        )
        records.append(record)

    succeeded = sum(1 for r in records if r.success)
    logger.info("Fetch complete: %s/%s succeeded", succeeded, len(records))
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    results = fetch_all()
    failed = [r.slug for r in results if not r.success]
    if failed:
        raise SystemExit(f"Fetch failed for: {', '.join(failed)}")
    print(f"Fetched {len(results)} schemes into {get_settings().data_raw_dir}")
