"""Persist and read daily scheduler run status."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import Settings, get_settings

STATUS_FILENAME = "scheduler_status.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.data_index_dir / STATUS_FILENAME


def read_status(settings: Settings | None = None) -> dict[str, Any]:
    path = status_path(settings)
    if not path.exists():
        return {"last_run": None, "last_success": None, "last_error": None, "runs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_run_result(
    *,
    success: bool,
    summary: dict[str, Any] | None = None,
    error: str | None = None,
    attempt: int = 1,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    path = status_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": _utc_now_iso(),
        "success": success,
        "attempt": attempt,
        "summary": summary,
        "error": error,
    }

    current = read_status(settings)
    runs = (current.get("runs") or [])[-19:]
    runs.append(record)

    payload = {
        "updated_at": _utc_now_iso(),
        "schedule": {
            "time": f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d}",
            "timezone": settings.scheduler_timezone,
        },
        "last_run": record["timestamp"],
        "last_success": record["timestamp"] if success else current.get("last_success"),
        "last_error": None if success else (error or "unknown error"),
        "runs": runs,
    }

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
