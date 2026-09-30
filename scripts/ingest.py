"""Run RAG stages 3 and 4 — Embed, then Store (PRD TR-2, TR-3).

Reads chunks/chunks.jsonl, embeds every chunk with MiniLM, and writes the
vectors into a persisted ChromaDB collection. Run once; the app never re-embeds
the corpus at startup.

    python scripts/ingest.py            # build, or skip if already current
    python scripts/ingest.py --force    # rebuild regardless
    python scripts/ingest.py --check    # report status, change nothing

Staleness. The collection records the corpus and chunk fingerprints it was
built from (ppfaq/pipeline/fingerprint.py). If the corpus has moved on but the
chunks have not been rebuilt, this refuses to run rather than embedding stale
text - a wrong figure with an official link under it is the worst output this
product has, and it would be invisible.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq import config  # noqa: E402
from ppfaq.pipeline.fingerprint import (  # noqa: E402
    CHUNKS_JSONL, StaleChunksError, chunks_fingerprint, corpus_fingerprint,
    require_fresh_chunks,
)

METADATA_FIELDS = ("scheme", "topic", "source_id", "source_title",
                   "source_url", "as_on", "part_index", "part_total")


def read_chunks():
    with open(CHUNKS_JSONL, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def open_client():
    try:
        import chromadb  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "the vector backend needs chromadb; install it with\n"
            "    pip install -r requirements-v2.txt"
        ) from exc
    os.makedirs(config.VECTORSTORE_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=config.VECTORSTORE_DIR)


def get_collection(client):
    """Fetch the existing collection, or None if there isn't one."""
    try:
        return client.get_collection(config.CHROMA_COLLECTION)
    except Exception:
        return None


def create_collection(client, corpus_fp: str, chunks_fp: str):
    """Create the collection with its full metadata in one go.

    Everything is set at creation because chromadb refuses to change the
    distance function afterwards - `modify()` with "hnsw:space" raises even
    when the value is unchanged. Cosine space must match Phase 5's
    `similarity = 1 - distance`.
    """
    return client.create_collection(
        name=config.CHROMA_COLLECTION,
        metadata={
            "hnsw:space": "cosine",
            "corpus_fingerprint": corpus_fp,
            "chunks_fingerprint": chunks_fp,
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dim": config.EMBEDDING_DIM,
        },
    )


def prune_orphan_segments() -> int:
    """Delete HNSW index folders left behind by dropped collections.

    chromadb's delete_collection() removes the sqlite rows but not the
    on-disk index, so every --force rebuild leaks a ~168 KB folder. Harmless
    to correctness - nothing references them - but the store grows without
    bound across rebuilds. Anything not named by a live segment id goes.
    """
    import shutil
    import sqlite3

    db = os.path.join(config.VECTORSTORE_DIR, "chroma.sqlite3")
    if not os.path.exists(db):
        return 0

    con = sqlite3.connect(db, timeout=5)
    try:
        live = {row[0] for row in con.execute("SELECT id FROM segments")}
    except sqlite3.Error:
        return 0
    finally:
        con.close()

    removed = 0
    for name in os.listdir(config.VECTORSTORE_DIR):
        path = os.path.join(config.VECTORSTORE_DIR, name)
        if os.path.isdir(path) and name not in live:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def describe(collection) -> str:
    meta = collection.metadata or {}
    return (f"{collection.count()} vectors, corpus "
            f"{str(meta.get('corpus_fingerprint'))[:12]}, chunks "
            f"{str(meta.get('chunks_fingerprint'))[:12]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed chunks into ChromaDB")
    parser.add_argument("--force", action="store_true",
                        help="rebuild even if the store is already current")
    parser.add_argument("--check", action="store_true",
                        help="report status and exit; change nothing")
    args = parser.parse_args()

    # -- refuse to embed chunks that predate the current corpus -------------
    try:
        manifest = require_fresh_chunks()
    except StaleChunksError as exc:
        print("STALE CHUNKS\n  %s" % exc)
        return 1

    want_chunks = chunks_fingerprint()
    want_corpus = corpus_fingerprint()

    # Prune before opening the store, while the on-disk state is settled. Doing
    # it after a rebuild does not work: the client still holds the store, and
    # the just-dropped segment is not yet visible as deleted to a separate
    # sqlite connection, so its folder survives the sweep.
    orphans = prune_orphan_segments()

    client = open_client()
    collection = get_collection(client)

    if collection is not None:
        stored = (collection.metadata or {}).get("chunks_fingerprint")
        current = stored == want_chunks and collection.count() > 0
        if args.check:
            print("store    %s" % describe(collection))
            print("chunks   %s" % want_chunks[:12])
            print("status   %s" % ("current" if current else "STALE - re-run ingest"))
            return 0 if current else 1
        if current and not args.force:
            print("store already current (%s)" % describe(collection))
            print("nothing to do; use --force to rebuild")
            return 0
        client.delete_collection(config.CHROMA_COLLECTION)
        collection = None
    elif args.check:
        print("no collection at %s - run: python scripts/ingest.py"
              % config.VECTORSTORE_DIR)
        return 1

    # -- stage 3: embed -----------------------------------------------------
    from ppfaq.embedding import embed  # lazy: keeps torch off the v1 path

    chunks = read_chunks()
    if not chunks:
        print("chunks.jsonl is empty - run: python scripts/build_chunks.py")
        return 1

    started = time.time()
    texts = [c["text"] for c in chunks]
    print("stage 3  embed  %d chunks with %s ..." % (len(texts), config.EMBEDDING_MODEL))
    vectors = embed(texts, show_progress=False)
    embed_seconds = time.time() - started

    # -- stage 4: store -----------------------------------------------------
    collection = create_collection(client, want_corpus, want_chunks)
    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=vectors,
        documents=texts,
        metadatas=[{k: c[k] for k in METADATA_FIELDS} for c in chunks],
    )

    total = time.time() - started
    print("stage 4  store  %d vectors -> %s" % (collection.count(), config.VECTORSTORE_DIR))
    if orphans:
        print("         pruned %d orphaned index folder(s) from earlier builds" % orphans)
    print("         dim    %d   collection %r   space cosine"
          % (len(vectors[0]), config.CHROMA_COLLECTION))
    print("         time   %.1fs embed, %.1fs total" % (embed_seconds, total))
    print("         stamp  corpus %s  chunks %s" % (want_corpus[:12], want_chunks[:12]))

    if collection.count() != len(chunks):
        print("ERROR: stored %d vectors but had %d chunks"
              % (collection.count(), len(chunks)))
        return 1
    if manifest.get("chunk_count") != len(chunks):
        print("WARNING: manifest says %s chunks, chunks.jsonl has %d"
              % (manifest.get("chunk_count"), len(chunks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
