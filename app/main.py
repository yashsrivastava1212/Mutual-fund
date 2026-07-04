"""FastAPI entrypoint — health, corpus, chat API, UI, and scheduler."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import __version__
from app.chat import handle_chat
from app.rate_limit import RateLimiter
from app.security import validate_message
from config.settings import get_settings, load_corpus
from scheduler.status import read_status

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = PROJECT_ROOT / "ui"

settings = get_settings()
rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    if settings.scheduler_enabled:
        from scheduler.daily import start_background_scheduler

        _scheduler = start_background_scheduler()
        logger.info("Background scheduler enabled")
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")


app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description="Facts-only RAG assistant for HDFC schemes (Groww corpus).",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_configured: bool
    llm_provider: str
    llm_model: str
    corpus_schemes: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    answer: str
    citation_url: str
    last_updated: str
    is_refusal: bool
    disclaimer: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    corpus = load_corpus()
    return HealthResponse(
        status="ok",
        version=__version__,
        llm_configured=settings.llm_configured,
        llm_provider="groq",
        llm_model=settings.llm_model,
        corpus_schemes=len(corpus["schemes"]),
    )


@app.get("/api/corpus")
def get_corpus_summary() -> dict:
    """Return public corpus metadata (no secrets)."""
    corpus = load_corpus()
    return {
        "amc": corpus.get("amc"),
        "source": corpus.get("source"),
        "schemes": [
            {
                "slug": s["slug"],
                "scheme_name": s["scheme_name"],
                "category": s["category"],
                "source_url": s["source_url"],
            }
            for s in corpus["schemes"]
        ],
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request_body: ChatRequest, request: Request) -> ChatResponse:
    """Classify query, run RAG or refusal path, return structured response."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")

    sanitized, error = validate_message(
        request_body.message,
        max_length=settings.max_message_length,
    )
    if error:
        raise HTTPException(status_code=400, detail=error)

    logger.info("Chat request from %s (%s chars)", client_ip, len(sanitized))
    try:
        result = handle_chat(sanitized)
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Backend error. Ensure GROQ_API_KEY is set and ingestion has run on Railway.",
        ) from exc


@app.get("/api/scheduler/status")
def scheduler_status() -> dict[str, Any]:
    """Return last scheduled ingestion run metadata."""
    status = read_status()
    status["enabled"] = settings.scheduler_enabled
    status["next_schedule"] = {
        "hour": settings.scheduler_hour,
        "minute": settings.scheduler_minute,
        "timezone": settings.scheduler_timezone,
        "label": f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} {settings.scheduler_timezone}",
    }
    return status


@app.get("/")
def serve_ui() -> FileResponse:
    """Serve the Phase 6 chat UI."""
    index_path = UI_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index_path)


@app.get("/app.js")
def serve_app_js() -> FileResponse:
    """Serve app.js at root so index.html can use ./app.js locally and on Vercel."""
    js_path = UI_DIR / "app.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="app.js not found")
    return FileResponse(js_path, media_type="application/javascript")


if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
