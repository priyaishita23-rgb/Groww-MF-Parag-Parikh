"""Retrieval backends and the factory that picks one.

    from ppfaq.retrieval import get_retriever
    retriever = get_retriever(chunks, schemes)      # honours RETRIEVER_BACKEND

Backends are selected by `ppfaq.config.RETRIEVER_BACKEND`, so nothing above this
package needs to know which one is running.

Import discipline: the vector backend is imported **inside** `get_retriever`,
never at module level. `ppfaq/__init__.py` imports `Assistant`, which reaches
here, so a module-level `from .vector import ...` would make torch and chromadb
a hard requirement of the zero-install v1 path (IMPLEMENTATION.md rule R5,
guarded by tests/test_zero_install.py).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .. import config
from ..corpus import Chunk, Scheme
from .base import BaseRetriever, Hit
from .schemes import detect_schemes
from .tfidf import TfidfRetriever, tokenize

__all__ = [
    "BaseRetriever", "Hit", "TfidfRetriever",
    "detect_schemes", "tokenize", "get_retriever",
]


def get_retriever(chunks: List[Chunk], schemes: Dict[str, Scheme],
                  backend: Optional[str] = None) -> BaseRetriever:
    """Build the configured retrieval backend.

    `backend` overrides `config.RETRIEVER_BACKEND`; tests use it to exercise both
    without touching the environment.
    """
    name = (backend or config.RETRIEVER_BACKEND or "").strip().lower()

    if name == config.TFIDF:
        return TfidfRetriever(chunks, schemes)

    if name == config.VECTOR:
        # Imported here, never at module level: this line is what would
        # otherwise drag torch and chromadb into the zero-install v1 path.
        from .vector import VectorRetriever

        return VectorRetriever(chunks, schemes)

    raise ValueError(
        f"unknown retrieval backend {name!r}; expected one of {', '.join(config.BACKENDS)}"
    )
