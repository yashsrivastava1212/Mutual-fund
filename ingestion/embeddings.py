"""Local embedding generation via sentence-transformers (BGE, free)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from config.embedding_models import (
    BGE_QUERY_INSTRUCTION,
    EmbeddingModelSpec,
    get_model_spec,
)
from config.settings import Settings, get_settings


@lru_cache
def get_embedding_model(model_name: str) -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _encode(texts: list[str], spec: EmbeddingModelSpec) -> list[list[float]]:
    model = get_embedding_model(spec.name)
    vectors = model.encode(
        texts,
        show_progress_bar=False,
        normalize_embeddings=spec.normalize,
    )
    return [vector.tolist() for vector in vectors]


def embed_documents(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """Embed corpus chunks / documents (no query prefix)."""
    if not texts:
        return []
    settings = settings or get_settings()
    spec = get_model_spec(settings.embedding_model)
    return _encode(texts, spec)


def embed_query(query: str, settings: Settings | None = None) -> list[float]:
    """Embed a user query; applies BGE query instruction when configured."""
    settings = settings or get_settings()
    spec = get_model_spec(settings.embedding_model)
    text = query
    if spec.use_query_instruction:
        text = BGE_QUERY_INSTRUCTION + query
    return _encode([text], spec)[0]


def embed_texts(texts: list[str], settings: Settings | None = None) -> list[list[float]]:
    """Backward-compatible alias for document embedding."""
    return embed_documents(texts, settings)


def get_embedding_dimensions(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    return get_model_spec(settings.embedding_model).dimensions
