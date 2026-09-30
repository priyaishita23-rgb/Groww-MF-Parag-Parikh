"""RAG stage 3 — Embed. MiniLM, loaded lazily (PRD TR-2).

`sentence_transformers` is imported **inside** `get_model()`, never at module
level. `ppfaq/__init__.py` imports `Assistant`, so a top-level import here would
drag torch into the zero-install v1 path (IMPLEMENTATION.md R5, guarded by
tests/test_zero_install.py).

The same model must embed the chunks and the queries — a store built with one
model and queried with another returns confident nonsense, so the model name
lives in config and the dimension is asserted on every call.

    from ppfaq.embedding import embed
    vectors = embed(["some text"])      # -> [[384 floats]]
"""

from __future__ import annotations

from typing import List, Optional

from . import config

_MODEL = None  # process-wide singleton; loading MiniLM takes a second or two


def get_model():
    """Load (once) and return the SentenceTransformer."""
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "the vector backend needs sentence-transformers; install it with\n"
                "    pip install -r requirements-v2.txt"
            ) from exc
        _MODEL = SentenceTransformer(config.EMBEDDING_MODEL)
    return _MODEL


def embed(texts: List[str], batch_size: int = 32,
          show_progress: bool = False) -> List[List[float]]:
    """Embed `texts` with MiniLM. Returns one 384-float vector per text.

    all-MiniLM-L6-v2 ends in a Normalize layer, so the vectors come back at
    unit length (confirmed in chunks/embeddings.txt: every norm is 1.0000).
    Cosine similarity is therefore just the dot product, and the Chroma
    collection's cosine space gives `similarity = 1 - distance`.
    """
    if not texts:
        return []

    model = get_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    dim = int(vectors.shape[1])
    if dim != config.EMBEDDING_DIM:
        raise ValueError(
            "%s produced %d-dimensional vectors, expected %d. The store and the "
            "queries must use the same model."
            % (config.EMBEDDING_MODEL, dim, config.EMBEDDING_DIM)
        )

    return [v.tolist() for v in vectors]


def embed_one(text: str) -> List[float]:
    """Convenience wrapper for the single-query path."""
    return embed([text])[0]
