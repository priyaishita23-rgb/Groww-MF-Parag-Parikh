"""Runtime configuration: which retrieval backend to use, and where v2 keeps its
derived files.

Imports `os` and nothing else, on purpose. This module is reachable from
`import ppfaq`, so anything heavier imported here would make torch and chromadb a
requirement of the zero-install v1 demo path (IMPLEMENTATION.md rule R5).

Select the backend with an environment variable:

    RETRIEVER_BACKEND=vector python app.py          # bash
    $env:RETRIEVER_BACKEND="vector"; python app.py  # PowerShell
"""

from __future__ import annotations

import os

# --- paths ------------------------------------------------------------------
# Resolved from the repo root the same way ppfaq/corpus.py does, so the package
# works regardless of the current working directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHUNKS_DIR = os.path.join(ROOT, "chunks")
VECTORSTORE_DIR = os.path.join(ROOT, "vectorstore")

# --- retrieval backend ------------------------------------------------------
TFIDF = "tfidf"
VECTOR = "vector"
BACKENDS = (TFIDF, VECTOR)

RETRIEVER_BACKEND = (os.environ.get("RETRIEVER_BACKEND") or TFIDF).strip().lower()

if RETRIEVER_BACKEND not in BACKENDS:
    # Fail loudly rather than silently falling back to tfidf. A typo that quietly
    # ran the wrong backend would be worst during Phase 6 calibration, where it
    # would produce a threshold measured against the backend you were not testing.
    raise ValueError(
        f"RETRIEVER_BACKEND={os.environ.get('RETRIEVER_BACKEND')!r} is not valid; "
        f"expected one of {', '.join(BACKENDS)}"
    )

# --- embeddings (v2 only; unused while RETRIEVER_BACKEND == 'tfidf') ---------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHROMA_COLLECTION = "mf_facts"
