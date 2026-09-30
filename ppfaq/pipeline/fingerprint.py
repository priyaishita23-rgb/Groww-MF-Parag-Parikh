"""Fingerprints that make a stale index detectable.

ARCHITECTURE.md §11 lists "Chroma persistence can drift from an edited corpus"
as a v2 risk, and it is the nastiest kind: a stale vector store answers
confidently with a figure the corpus no longer contains, and nothing looks
broken. Ingestion is a build step run by hand, so drift is a matter of when.

Two fingerprints, because there are two different ways to drift:

    corpus  = sha256(corpus.json + schemes.json + sources.csv)
    chunks  = sha256(chunks.jsonl)

`chunks/manifest.json` records which corpus fingerprint the chunks were built
from. That is what distinguishes the two failures:

  * corpus edited, chunks not rebuilt  -> manifest's corpus fingerprint is stale
                                          -> ingest refuses; run build_chunks.py
  * chunks rebuilt, store not re-ingested -> chunks fingerprint differs
                                          -> ingest re-embeds
  * nothing changed                    -> both match, ingest is a no-op

A single combined hash could not tell the first case from the third.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional

from .. import config
from ..corpus import CORPUS_DIR

MANIFEST = os.path.join(config.CHUNKS_DIR, "manifest.json")
CHUNKS_JSONL = os.path.join(config.CHUNKS_DIR, "chunks.jsonl")

#: Files that define the corpus. Order is fixed so the hash is reproducible.
CORPUS_FILES = ["corpus.json", "schemes.json", "sources.csv"]


def _sha256(paths: List[str]) -> str:
    """Hash file contents, normalised so line endings cannot change the result.

    Hashing raw bytes looked right and was wrong. Git rewrites line endings on
    checkout, so cloning this repo on Windows turns every LF into CRLF, the
    digest changes, and a correct store is rejected as stale before the first
    question is asked. The corpus is identical either way; the bytes are not.
    CRLF and a lone CR both collapse to LF before hashing.
    """
    digest = hashlib.sha256()
    for path in paths:
        # Hash the name too, so reordering or renaming is visible.
        digest.update(os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as fh:
            content = fh.read()
        digest.update(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return digest.hexdigest()


def corpus_fingerprint() -> str:
    """Hash of the source-of-truth files."""
    return _sha256([os.path.join(CORPUS_DIR, name) for name in CORPUS_FILES])


def chunks_fingerprint() -> str:
    """Hash of the derived chunk file."""
    return _sha256([CHUNKS_JSONL])


def write_manifest(chunk_count: int, max_chars: int) -> Dict[str, object]:
    """Record what the chunks were built from, next to the chunks."""
    manifest = {
        "corpus_fingerprint": corpus_fingerprint(),
        "chunks_fingerprint": chunks_fingerprint(),
        "chunk_count": chunk_count,
        "max_chars": max_chars,
        "embedding_model": config.EMBEDDING_MODEL,
        "embedding_dim": config.EMBEDDING_DIM,
    }
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    return manifest


def read_manifest() -> Optional[Dict[str, object]]:
    if not os.path.exists(MANIFEST):
        return None
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


class StaleChunksError(RuntimeError):
    """Chunks on disk were built from a different corpus than the one present."""


def require_fresh_chunks() -> Dict[str, object]:
    """Return the manifest, or raise if the chunks are missing or stale."""
    manifest = read_manifest()
    if manifest is None:
        raise StaleChunksError(
            "no chunks/manifest.json - run: python scripts/build_chunks.py"
        )
    if not os.path.exists(CHUNKS_JSONL):
        raise StaleChunksError(
            "no chunks/chunks.jsonl - run: python scripts/build_chunks.py"
        )
    current = corpus_fingerprint()
    if manifest.get("corpus_fingerprint") != current:
        raise StaleChunksError(
            "the corpus has changed since the chunks were built.\n"
            "  chunks were built from corpus %s\n"
            "  corpus on disk is           %s\n"
            "  run: python scripts/build_chunks.py"
            % (str(manifest.get("corpus_fingerprint"))[:12], current[:12])
        )
    return manifest
