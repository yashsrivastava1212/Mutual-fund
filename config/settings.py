"""Application settings and corpus loader."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from config.embedding_models import BGE_SMALL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_PATH = PROJECT_ROOT / "config" / "corpus.yaml"


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    llm_model: str
    llm_timeout_seconds: int
    llm_max_tokens: int
    llm_temperature: float
    max_message_length: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    corpus_path: Path
    data_raw_dir: Path
    data_processed_dir: Path
    data_chunks_dir: Path
    data_index_dir: Path
    lance_db_uri: Path
    scheme_metadata_path: Path
    index_staging_dir: Path
    embedding_model: str
    embedding_preset: str
    api_host: str
    api_port: int
    scheduler_enabled: bool
    scheduler_hour: int
    scheduler_minute: int
    scheduler_timezone: str
    scheduler_max_retries: int
    scheduler_retry_delay_seconds: int
    ingest_on_startup: bool

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("XAI_API_KEY", "").strip()
    llm_model = (
        os.getenv("GROQ_MODEL", "").strip()
        or os.getenv("GROK_MODEL", "").strip()
        or "llama-3.3-70b-versatile"
    )
    return Settings(
        groq_api_key=groq_api_key,
        llm_model=llm_model,
        llm_timeout_seconds=int(
            os.getenv("GROQ_TIMEOUT_SECONDS") or os.getenv("GROK_TIMEOUT_SECONDS", "120")
        ),
        llm_max_tokens=int(
            os.getenv("GROQ_MAX_TOKENS") or os.getenv("GROK_MAX_TOKENS", "512")
        ),
        llm_temperature=float(
            os.getenv("GROQ_TEMPERATURE") or os.getenv("GROK_TEMPERATURE", "0.1")
        ),
        max_message_length=int(os.getenv("MAX_MESSAGE_LENGTH", "2000")),
        rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "30")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        corpus_path=Path(os.getenv("CORPUS_PATH", str(DEFAULT_CORPUS_PATH))),
        data_raw_dir=PROJECT_ROOT / "data" / "raw",
        data_processed_dir=PROJECT_ROOT / "data" / "processed",
        data_chunks_dir=PROJECT_ROOT / "data" / "processed" / "chunks",
        data_index_dir=PROJECT_ROOT / "data" / "index",
        lance_db_uri=PROJECT_ROOT / "data" / "index" / "lancedb",
        scheme_metadata_path=PROJECT_ROOT / "data" / "index" / "scheme_metadata.json",
        index_staging_dir=PROJECT_ROOT / "data" / "index" / "staging",
        embedding_model=os.getenv("EMBEDDING_MODEL", BGE_SMALL).strip(),
        embedding_preset=os.getenv("EMBEDDING_PRESET", "auto").strip(),
        api_host=os.getenv("API_HOST", "0.0.0.0").strip(),
        api_port=int(os.getenv("PORT") or os.getenv("API_PORT", "8000")),
        scheduler_enabled=os.getenv("SCHEDULER_ENABLED", "false").strip().lower() in ("1", "true", "yes"),
        scheduler_hour=int(os.getenv("SCHEDULER_HOUR", "10")),
        scheduler_minute=int(os.getenv("SCHEDULER_MINUTE", "0")),
        scheduler_timezone=os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata").strip(),
        scheduler_max_retries=int(os.getenv("SCHEDULER_MAX_RETRIES", "2")),
        scheduler_retry_delay_seconds=int(os.getenv("SCHEDULER_RETRY_DELAY_SECONDS", "60")),
        ingest_on_startup=os.getenv("INGEST_ON_STARTUP", "false").strip().lower() in ("1", "true", "yes"),
    )


def load_corpus(corpus_path: Path | None = None) -> dict[str, Any]:
    path = corpus_path or get_settings().corpus_path
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "schemes" not in data:
        raise ValueError(f"Invalid corpus file: {path}")
    if len(data["schemes"]) != 5:
        raise ValueError(f"Corpus must contain exactly 5 schemes, found {len(data['schemes'])}")
    return data
