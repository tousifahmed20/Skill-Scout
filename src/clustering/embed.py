"""Embedder (stage 05). Runs only in the GitHub Actions build (CLAUDE.md: the
shipped skill never embeds — it searches text). sentence-transformers is a CI
dependency, imported lazily so importing this package for `search`/`cluster`
never pulls it in.

Recorded model (CLAUDE.md asks stage 05 to pick and record it):
    sentence-transformers/all-MiniLM-L6-v2 — small, CPU-friendly, 384-dim,
    widely used for semantic similarity. Change via docs/decisions.md.
"""
from __future__ import annotations

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
MAX_TOKENS = 300            # CONTEXT.md: name + description + first section, capped

_model = None


def _load():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer   # lazy: CI only
        _model = SentenceTransformer(MODEL)
    return _model


def embed_text(name: str, description: str, first_section: str) -> str:
    text = f"{name}\n{description}\n{first_section}".strip()
    return " ".join(text.split()[:MAX_TOKENS])


def embed(texts: list[str]) -> list[list[float]]:
    """Normalized embedding vectors (so cosine == dot product)."""
    vecs = _load().encode(texts, normalize_embeddings=True)
    return [[float(x) for x in v] for v in vecs]
