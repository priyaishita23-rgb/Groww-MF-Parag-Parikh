"""Write the stored vectors out as readable text (RAG stage 3, inspectable).

The vectors live inside ChromaDB as binary. This dumps them to
chunks/embeddings.txt so the embedding stage can be read and shown, the same
way chunks/chunks.txt does for the chunking stage.

    python scripts/export_embeddings.py

The file has three parts:
  1. a summary table  - one line per chunk, with vector statistics
  2. the full vectors - all 384 dimensions of every chunk
  3. nearest neighbours - which chunks the model thinks are alike, which is
     the part that actually shows whether the embedding is doing its job
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq import config  # noqa: E402
from ppfaq.pipeline.fingerprint import read_manifest  # noqa: E402

OUT = os.path.join(config.CHUNKS_DIR, "embeddings.txt")
PER_LINE = 6
RULE = "-" * 78


def main() -> int:
    try:
        import chromadb  # noqa: PLC0415
    except ImportError:
        print("needs chromadb: pip install -r requirements-v2.txt")
        return 1

    if not os.path.isdir(config.VECTORSTORE_DIR):
        print("no vectorstore/ - run: python scripts/ingest.py")
        return 1

    client = chromadb.PersistentClient(path=config.VECTORSTORE_DIR)
    try:
        col = client.get_collection(config.CHROMA_COLLECTION)
    except Exception:
        print("no collection %r - run: python scripts/ingest.py"
              % config.CHROMA_COLLECTION)
        return 1

    got = col.get(include=["embeddings", "documents", "metadatas"])
    ids = got["ids"]
    vectors = got["embeddings"]
    documents = got["documents"]
    metadatas = got["metadatas"]

    # Natural sort, so C11 comes before C100 rather than after it.
    def natural(cid: str):
        m = re.match(r"([A-Za-z]*)(\d*)(.*)", cid)
        return (m.group(1), int(m.group(2) or 0), m.group(3))

    order = sorted(range(len(ids)), key=lambda i: natural(ids[i]))
    ids = [ids[i] for i in order]
    vectors = [list(map(float, vectors[i])) for i in order]
    documents = [documents[i] for i in order]
    metadatas = [metadatas[i] for i in order]

    manifest = read_manifest() or {}
    meta = col.metadata or {}
    dim = len(vectors[0])

    def norm(v):
        return sum(x * x for x in v) ** 0.5

    def cosine(a, b):
        na, nb = norm(a), norm(b)
        if not na or not nb:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / (na * nb)

    lines = []
    w = lines.append

    # ---- header -----------------------------------------------------------
    w("=" * 78)
    w("RAG STAGE 3 - EMBED     vectors as stored in ChromaDB")
    w("=" * 78)
    w("Model              %s" % config.EMBEDDING_MODEL)
    w("Dimensions         %d" % dim)
    w("Chunks embedded    %d" % len(ids))
    w("Distance space     %s" % meta.get("hnsw:space"))
    w("Collection         %s" % config.CHROMA_COLLECTION)
    w("Store              %s" % config.VECTORSTORE_DIR)
    w("Corpus fingerprint %s" % manifest.get("corpus_fingerprint"))
    w("Chunks fingerprint %s" % manifest.get("chunks_fingerprint"))
    w("Exported           %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    w("")
    w("Each chunk of text below was turned into %d numbers by MiniLM. Text that" % dim)
    w("means similar things lands close together in that %d-dimensional space," % dim)
    w("which is what makes search by meaning possible. The numbers themselves are")
    w("not interpretable one by one - part 3 is where you can see them working.")
    w("")

    # ---- part 1: summary --------------------------------------------------
    w("=" * 78)
    w("1. SUMMARY - one line per chunk")
    w("=" * 78)
    w("%-6s %-7s %-24s %9s %9s %9s %9s" %
      ("id", "scheme", "topic", "norm", "min", "max", "mean"))
    w(RULE)
    for cid, vec, md in zip(ids, vectors, metadatas):
        w("%-6s %-7s %-24s %9.4f %9.4f %9.4f %9.4f" %
          (cid, md["scheme"], md["topic"], norm(vec),
           min(vec), max(vec), sum(vec) / len(vec)))
    w("")

    # ---- part 2: full vectors --------------------------------------------
    w("=" * 78)
    w("2. FULL VECTORS - all %d dimensions of every chunk" % dim)
    w("=" * 78)
    w("")
    for cid, vec, doc, md in zip(ids, vectors, documents, metadatas):
        w(RULE)
        w("[%s]  %s - %s - %s" % (cid, md["scheme"], md["topic"], md["source_id"]))
        w(RULE)
        for line in doc.splitlines():
            w("  | %s" % line)
        w("")
        w("  vector (%d dims, L2 norm %.4f):" % (dim, norm(vec)))
        for start in range(0, dim, PER_LINE):
            row = vec[start:start + PER_LINE]
            w("  [%3d] %s" % (start, "  ".join("%+.6f" % x for x in row)))
        w("")

    # ---- part 3: nearest neighbours --------------------------------------
    w("=" * 78)
    w("3. NEAREST NEIGHBOURS - what the model thinks is similar")
    w("=" * 78)
    w("")
    w("Cosine similarity between chunk vectors. This is the useful view: if the")
    w("embedding is working, a fact's closest neighbours are the same fact for")
    w("other schemes, or related facts for the same scheme.")
    w("")
    for i, (cid, vec, md) in enumerate(zip(ids, vectors, metadatas)):
        sims = sorted(
            ((cosine(vec, vectors[j]), ids[j], metadatas[j])
             for j in range(len(ids)) if j != i),
            reverse=True,
        )[:3]
        w("[%s] %s - %s" % (cid, md["scheme"], md["topic"]))
        for sim, oid, omd in sims:
            w("      %.4f  %-6s %-7s %s" % (sim, oid, omd["scheme"], omd["topic"]))
    w("")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))

    size = os.path.getsize(OUT)
    print("wrote %s" % OUT)
    print("      %d chunks x %d dims, %.0f KB" % (len(ids), dim, size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
