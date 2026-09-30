"""Vector retrieval over the persisted ChromaDB store (PRD TR-4).

The v2 backend. It replaces *how a chunk is found* and nothing else: the
answer still comes from the corpus record the hit points at, so the citation
contract (FR-11) holds by the same mechanism as v1 (ARCHITECTURE §4.1, §11).

Three things are deliberately identical to the TF-IDF backend:

  * **Scheme detection** - the same exact-alias function, not embeddings
    (ppfaq/retrieval/schemes.py). Whether a question is about the ELSS or the
    Flexi Cap is a lookup, not a similarity judgement.
  * **The hard filter** - a named scheme becomes a Chroma `where` clause, so
    other schemes are never scored. This matters *more* here than in v1: the
    five sibling funds' chunks sit at 0.92-0.95 cosine of each other
    (chunks/embeddings.txt, part 3), because MiniLM clusters by topic rather
    than by fund. Without the filter, a wrong-fund answer is the default.
  * **The scoring bias** - +0.25 / +0.05 / -0.10, unchanged, so ranking
    behaves the way the assistant's clarify and follow-up logic expects.

What differs is the base similarity: cosine from MiniLM instead of TF-IDF.
That means `MIN_SCORE` does **not** transfer - Phase 6 recalibrates it.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from .. import config
from ..corpus import Chunk, Scheme
from .base import BaseRetriever, Hit
from .schemes import detect_schemes as _detect_schemes


class VectorStoreUnavailable(RuntimeError):
    """The persisted store is missing, empty, or built from another corpus."""


class VectorRetriever(BaseRetriever):
    """MiniLM + ChromaDB, behind the same hard scheme filter as v1."""

    #: How many candidates to pull before applying the bias. The bias can
    #: reorder results, so truncating to k first would let it rearrange an
    #: already-wrong shortlist.
    OVERFETCH = 4

    def __init__(self, chunks: List[Chunk], schemes: Dict[str, Scheme]):
        self.chunks = chunks
        self.schemes = schemes
        self._by_id: Dict[str, Chunk] = {c.id: c for c in chunks}
        self._collection = self._open()

    # -- store -------------------------------------------------------------
    def _open(self):
        from ..pipeline.fingerprint import corpus_fingerprint

        try:
            import chromadb  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise VectorStoreUnavailable(
                "the vector backend needs chromadb:\n"
                "    pip install -r requirements-v2.txt"
            ) from exc

        if not os.path.isdir(config.VECTORSTORE_DIR):
            raise VectorStoreUnavailable(
                "no vector store at %s\n"
                "    python scripts/build_chunks.py && python scripts/ingest.py"
                % config.VECTORSTORE_DIR
            )

        client = chromadb.PersistentClient(path=config.VECTORSTORE_DIR)
        try:
            collection = client.get_collection(config.CHROMA_COLLECTION)
        except Exception as exc:
            raise VectorStoreUnavailable(
                "no collection %r in %s\n"
                "    python scripts/ingest.py"
                % (config.CHROMA_COLLECTION, config.VECTORSTORE_DIR)
            ) from exc

        if collection.count() == 0:
            raise VectorStoreUnavailable(
                "the collection is empty - run: python scripts/ingest.py"
            )

        # A store built from a different corpus would answer with figures the
        # corpus no longer contains, under a citation that looks official.
        # Refuse rather than serve it (ARCHITECTURE §11).
        stored = (collection.metadata or {}).get("corpus_fingerprint")
        current = corpus_fingerprint()
        if stored != current:
            raise VectorStoreUnavailable(
                "the vector store was built from a different corpus.\n"
                "    store  %s\n"
                "    corpus %s\n"
                "    python scripts/build_chunks.py && python scripts/ingest.py --force"
                % (str(stored)[:12], current[:12])
            )
        return collection

    # -- scheme detection --------------------------------------------------
    def detect_schemes(self, question: str) -> List[str]:
        return _detect_schemes(question, self.schemes)

    # -- search ------------------------------------------------------------
    def search(self, question: str, scheme: Optional[str] = None,
               k: int = 3) -> List[Hit]:
        from ..embedding import embed_one  # lazy: keeps torch off the v1 path

        if not (question or "").strip():
            return []

        where = None
        if scheme is not None:
            # The hard filter. Other schemes are never scored.
            where = {"scheme": {"$in": [scheme, "ALL"]}}

        n = min(max(k * self.OVERFETCH, k), self._collection.count())
        result = self._collection.query(
            query_embeddings=[embed_one(question)],
            n_results=n,
            where=where,
            include=["distances", "metadatas"],
        )

        ids = result["ids"][0]
        distances = result["distances"][0]
        metadatas = result["metadatas"][0]

        # A corpus record split into parts contributes several chunks; keep the
        # best-scoring part, because the Hit carries the whole record anyway.
        best: Dict[str, tuple] = {}
        for chunk_id, distance, metadata in zip(ids, distances, metadatas):
            corpus_id = chunk_id.split("-")[0]
            chunk = self._by_id.get(corpus_id)
            if chunk is None:
                # The store holds an id the corpus no longer has. The
                # fingerprint check in _open should make this unreachable;
                # skipping is the safe response if it ever is not.
                continue

            raw = 1.0 - float(distance)            # cosine space
            score = raw
            chunk_scheme = metadata.get("scheme")

            if scheme is not None and chunk_scheme == scheme:
                score += 0.25      # prefer the named scheme over generic chunks
            elif scheme is not None and chunk_scheme == "ALL":
                score += 0.05
            elif scheme is None and chunk_scheme != "ALL":
                score -= 0.10      # ambiguous question, generic facts first

            previous = best.get(corpus_id)
            if score > 0 and (previous is None or score > previous[0]):
                best[corpus_id] = (score, raw)

        hits = [Hit(self._by_id[cid], score, raw)
                for cid, (score, raw) in best.items()]
        hits.sort(key=lambda h: (-h.score, h.chunk.id))
        return hits[:k]
