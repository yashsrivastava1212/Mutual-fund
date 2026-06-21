"""Ingestion orchestration: fetch → parse → chunk → index."""

from __future__ import annotations

import argparse
import logging
import sys

from config.settings import get_settings
from ingestion.chunk import chunk_all
from ingestion.fetch import fetch_all
from ingestion.index import index_all
from ingestion.parse import parse_all

logger = logging.getLogger(__name__)


def run_ingestion(
    *,
    skip_fetch: bool = False,
    skip_index: bool = False,
) -> dict:
    """Run the full offline ingestion pipeline."""
    settings = get_settings()
    summary: dict = {"steps": {}}

    if not skip_fetch:
        logger.info("Step 1/4: Fetching Groww scheme pages...")
        fetch_records = fetch_all(settings)
        summary["steps"]["fetch"] = {
            "total": len(fetch_records),
            "succeeded": sum(1 for r in fetch_records if r.success),
            "failed": [r.slug for r in fetch_records if not r.success],
        }
        if summary["steps"]["fetch"]["failed"]:
            raise RuntimeError(
                "Fetch failed for: " + ", ".join(summary["steps"]["fetch"]["failed"])
            )
    else:
        logger.info("Step 1/4: Fetch skipped")

    logger.info("Step 2/4: Parsing HTML into sections...")
    parsed = parse_all(settings)
    summary["steps"]["parse"] = {"schemes_parsed": len(parsed)}
    if not parsed:
        raise RuntimeError("Parse produced zero schemes")

    logger.info("Step 3/4: Chunking parsed sections...")
    chunks = chunk_all(settings)
    summary["steps"]["chunk"] = {"chunk_count": len(chunks)}
    if not chunks:
        raise RuntimeError("Chunking produced zero chunks")

    if not skip_index:
        logger.info("Step 4/4: Embedding and indexing into LanceDB...")
        index_summary = index_all(settings, chunks=chunks)
        summary["steps"]["index"] = index_summary
    else:
        logger.info("Step 4/4: Index skipped")

    logger.info("Ingestion pipeline complete")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run mutual fund ingestion pipeline")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetch step (use existing raw HTML)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip embed/index step (fetch, parse, chunk only)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        summary = run_ingestion(skip_fetch=args.skip_fetch, skip_index=args.skip_index)
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    chunk_count = summary["steps"].get("chunk", {}).get("chunk_count", 0)
    index_count = summary["steps"].get("index", {}).get("chunk_count", "skipped")
    print(f"Ingestion OK — chunks: {chunk_count}, indexed: {index_count}")


if __name__ == "__main__":
    main()
