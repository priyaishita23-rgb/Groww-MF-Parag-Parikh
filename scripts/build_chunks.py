"""Run RAG stages 1 and 2 — Load, then Chunk — and write inspectable output.

    python scripts/build_chunks.py

Writes:
    chunks/documents.txt   stage 1 report: what was loaded, and from where
    chunks/chunks.txt      stage 2, human-readable: exactly what gets embedded
    chunks/chunks.jsonl    stage 2, machine-readable: input to scripts/ingest.py

chunks.txt exists to be read. The brief requires the chunking strategy to be
inspectable, and a reviewer should be able to see every chunk without running
anything.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq import config  # noqa: E402
from ppfaq.chunking import (  # noqa: E402
    MAX_CHARS, SEPARATORS, build_chunk_documents, oversized,
)
from ppfaq.pipeline import describe_documents, load_documents  # noqa: E402
from ppfaq.pipeline.fingerprint import write_manifest  # noqa: E402

RULE = "-" * 78


def main() -> int:
    os.makedirs(config.CHUNKS_DIR, exist_ok=True)

    # -- stage 1: load ------------------------------------------------------
    documents = load_documents()
    report = describe_documents(documents)
    doc_path = os.path.join(config.CHUNKS_DIR, "documents.txt")
    with open(doc_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report)
    print(f"stage 1  load   {len(documents)} documents -> {doc_path}")

    # -- stage 2: chunk -----------------------------------------------------
    chunks = build_chunk_documents(documents)

    jsonl_path = os.path.join(config.CHUNKS_DIR, "chunks.jsonl")
    with open(jsonl_path, "w", encoding="utf-8", newline="\n") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

    txt_path = os.path.join(config.CHUNKS_DIR, "chunks.txt")
    lengths = [len(c.text) for c in chunks]
    split = [c for c in chunks if c.part_total > 1]
    ladder = " | ".join(repr(s) for s in SEPARATORS)
    with open(txt_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("=" * 78 + "\n")
        fh.write("RAG STAGE 2 - CHUNK\n")
        fh.write("=" * 78 + "\n")
        fh.write("Strategy         recursive section-aware, numeric conditions kept whole\n")
        fh.write(f"Max chars        {MAX_CHARS}\n")
        fh.write(f"Separator ladder {ladder}\n")
        fh.write("Overlap          none - every chunk repeats the scheme/topic header instead\n")
        fh.write(f"Documents in     {len(documents)}\n")
        fh.write(f"Chunks out       {len(chunks)}  ({len(split)} from split documents)\n")
        fh.write(f"Chars            min {min(lengths)}  mean {sum(lengths)//len(lengths)}  max {max(lengths)}\n")
        fh.write("\n")
        for chunk in chunks:
            fh.write(RULE + "\n")
            fh.write(f"[{chunk.chunk_id}]  {chunk.scheme} - {chunk.topic} - "
                     f"{chunk.source_id}  ({len(chunk.text)} chars")
            if chunk.part_total > 1:
                fh.write(f", part {chunk.part_index}/{chunk.part_total}")
            fh.write(")\n")
            fh.write(RULE + "\n")
            fh.write(chunk.text + "\n")
            fh.write(f"\nSource: {chunk.source_title}\n        {chunk.source_url}\n")
            fh.write(f"As on:  {chunk.as_on}\n\n")

    print(f"stage 2  chunk  {len(chunks)} chunks -> {txt_path}")
    print(f"                              -> {jsonl_path}")
    print(f"         sizes  min {min(lengths)}  mean {sum(lengths)//len(lengths)}  max {max(lengths)}")

    # -- stamp what these chunks were built from ---------------------------
    manifest = write_manifest(chunk_count=len(chunks), max_chars=MAX_CHARS)
    print(f"         stamp  corpus {str(manifest['corpus_fingerprint'])[:12]}  "
          f"chunks {str(manifest['chunks_fingerprint'])[:12]}")

    over = oversized(chunks)
    if over:
        print(f"\nWARNING  {len(over)} chunk(s) exceed {MAX_CHARS} chars with no legal "
              f"split point; left whole rather than cut mid-rule:")
        for chunk in over:
            print(f"         {chunk.chunk_id}  {len(chunk.text)} chars  ({chunk.topic})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
