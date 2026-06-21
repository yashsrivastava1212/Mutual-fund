"""RAG orchestrator using Groq LLM."""

from __future__ import annotations

from app.llm import LLMClient, get_llm_client

SYSTEM_PROMPT = """You are a facts-only mutual fund FAQ assistant for five HDFC scheme pages on Groww.

Rules:
- Answer ONLY using the provided context chunks. Do not use outside knowledge.
- If the context is insufficient, say so briefly and do not invent numbers or names.
- Maximum 3 short sentences in the answer body.
- Do NOT give investment advice, recommendations, or buy/sell/hold guidance.
- Do NOT compare funds or rank schemes.
- Do NOT calculate or project returns.
- Do NOT include URLs in your answer (citation is handled separately).
- Use plain, factual language."""


def build_context_block(chunks: list[dict]) -> str:
    """Format retrieved chunks for the LLM user prompt."""
    if not chunks:
        return "(No context retrieved.)"

    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[Chunk {index}]\n"
            f"Scheme: {chunk['scheme_name']}\n"
            f"Section: {chunk['section']}\n"
            f"Source: {chunk['source_url']}\n"
            f"Last updated: {chunk['last_updated']}\n"
            f"Text:\n{chunk['text']}"
        )
    return "\n\n".join(parts)


def build_user_prompt(message: str, chunks: list[dict]) -> str:
    context = build_context_block(chunks)
    return (
        f"Context:\n{context}\n\n"
        f"User question: {message}\n\n"
        "Answer the question using only the context above."
    )


def generate_answer(
    message: str,
    chunks: list[dict],
    llm: LLMClient | None = None,
) -> str:
    """Generate a grounded answer from retrieved chunks via Groq."""
    client = llm or get_llm_client()
    user_prompt = build_user_prompt(message, chunks)
    completion = client.complete_with_retry(SYSTEM_PROMPT, user_prompt)
    return completion.content.strip()
