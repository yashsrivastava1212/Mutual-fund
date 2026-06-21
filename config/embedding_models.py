"""BGE and other local embedding model configuration."""

from __future__ import annotations

from dataclasses import dataclass

# Free, local models via sentence-transformers (no OpenAI / text-embedding-3-small)
BGE_SMALL = "BAAI/bge-small-en-v1.5"
BGE_LARGE = "BAAI/bge-large-en-v1.5"

BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# Thresholds for auto preset (current corpus: 51 chunks, ~30 tokens avg, 65 max)
AUTO_LARGE_MIN_CHUNKS = 500
AUTO_LARGE_MIN_MAX_TOKENS = 400
AUTO_LARGE_MIN_AVG_TOKENS = 150


@dataclass(frozen=True)
class ChunkStats:
    count: int
    max_tokens: int
    avg_tokens: float


@dataclass(frozen=True)
class EmbeddingModelSpec:
    name: str
    dimensions: int
    normalize: bool
    use_query_instruction: bool


MODEL_SPECS: dict[str, EmbeddingModelSpec] = {
    BGE_SMALL: EmbeddingModelSpec(
        name=BGE_SMALL,
        dimensions=384,
        normalize=True,
        use_query_instruction=True,
    ),
    BGE_LARGE: EmbeddingModelSpec(
        name=BGE_LARGE,
        dimensions=1024,
        normalize=True,
        use_query_instruction=True,
    ),
}


def is_bge_model(model_name: str) -> bool:
    lowered = model_name.lower()
    return "bge-" in lowered or "baai/bge" in lowered


def get_model_spec(model_name: str) -> EmbeddingModelSpec:
    if model_name in MODEL_SPECS:
        return MODEL_SPECS[model_name]
    return EmbeddingModelSpec(
        name=model_name,
        dimensions=384,
        normalize=is_bge_model(model_name),
        use_query_instruction=is_bge_model(model_name),
    )


def compute_chunk_stats(chunks: list) -> ChunkStats:
    if not chunks:
        return ChunkStats(count=0, max_tokens=0, avg_tokens=0.0)
    counts = [len(c.text.split()) for c in chunks]
    return ChunkStats(
        count=len(counts),
        max_tokens=max(counts),
        avg_tokens=sum(counts) / len(counts),
    )


def recommend_bge_model(stats: ChunkStats) -> str:
    """Pick BGE-small vs BGE-large from chunk corpus statistics."""
    if stats.count >= AUTO_LARGE_MIN_CHUNKS:
        return BGE_LARGE
    if stats.max_tokens >= AUTO_LARGE_MIN_MAX_TOKENS:
        return BGE_LARGE
    if stats.avg_tokens >= AUTO_LARGE_MIN_AVG_TOKENS:
        return BGE_LARGE
    return BGE_SMALL


def resolve_embedding_model(
    *,
    explicit_model: str,
    preset: str,
    stats: ChunkStats | None = None,
) -> str:
    """
    Resolve embedding model name.

    EMBEDDING_PRESET:
    - auto  → BGE-small or BGE-large from chunk stats (default)
    - small → BAAI/bge-small-en-v1.5
    - large → BAAI/bge-large-en-v1.5
    - custom → EMBEDDING_MODEL env value
    """
    preset = (preset or "auto").lower().strip()
    explicit = (explicit_model or "").strip()

    if preset == "small":
        return BGE_SMALL
    if preset == "large":
        return BGE_LARGE
    if preset == "custom":
        return explicit or BGE_SMALL
    if preset == "auto":
        if stats is None:
            return BGE_SMALL
        return recommend_bge_model(stats)

    return explicit or BGE_SMALL
