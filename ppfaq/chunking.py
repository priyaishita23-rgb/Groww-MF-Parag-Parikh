"""RAG stage 2 — Chunk. Recursive section-aware chunking (PRD TR-1).

The corpus is already atomic: one record is one fact. So this stage is not
cutting prose into windows. It does two things.

**Builds the text that gets embedded.** Every chunk is stamped with a header
naming its scheme, fund house and topic. Under embeddings a chunk that does not
name its own fund is a wrong-fund answer waiting to happen: MiniLM will not
reliably separate two chunks that differ only in a proper noun. The hard scheme
filter (ARCHITECTURE §6.3) is the primary defence; the header is the cheap
second one.

**Splits the few records long enough to risk truncation.** MiniLM's window is
256 word-pieces, and anything past it is silently dropped — a fact that is
quietly half-embedded is worse than one that is split honestly.

Splitting is *section-aware*: it descends a ladder of separators, taking the
largest structural unit that works, and it refuses to cut a numeric rule apart.

    from ppfaq.chunking import build_chunk_documents
    chunks = build_chunk_documents(load_documents())
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from .pipeline.load import SourceDocument

#: Roughly 200 word-pieces, comfortably inside MiniLM's 256 limit.
MAX_CHARS = 900

#: Largest structural unit first; descend only when a piece is still too long.
SEPARATORS = ["\n\n", "\n", ". ", "; ", ", "]

#: A split is illegal if it would strand a number from the condition that
#: qualifies it. "0.0060%" alone is not a fact; "0.0060% if redeemed within 3
#: days" is. Everything before the separator ending in a number or percentage,
#: with the text after it opening a qualifying clause, is exactly that break.
_ENDS_WITH_NUMBER = re.compile(
    r"(?:\d|%|₹\s*[\d,]+|Rs\.?\s*[\d,]+)\s*$", re.I
)
_OPENS_CONDITION = re.compile(
    r"^\s*(?:if|when|within|after|before|upto|up to|on or before|in excess of|"
    r"for|per|days?|months?|years?|business days?)\b", re.I
)


@dataclass(frozen=True)
class ChunkDoc:
    """One embedding-ready chunk."""

    chunk_id: str
    text: str
    scheme: str
    topic: str
    source_id: str
    source_title: str
    source_url: str
    as_on: str
    part_index: int
    part_total: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _title(topic: str) -> str:
    return topic.replace("_", " ").capitalize()


def _header(doc: SourceDocument) -> str:
    if doc.scheme is not None:
        return f"Scheme: {doc.scheme.name} (PPFAS Mutual Fund)\nTopic: {_title(doc.topic)}"
    return f"Scheme: All PPFAS schemes\nTopic: {_title(doc.topic)}"


def _split_is_legal(left: str, right: str) -> bool:
    """False if cutting here would strand a number from its condition."""
    return not (_ENDS_WITH_NUMBER.search(left) and _OPENS_CONDITION.match(right))


def _split_once(text: str, separator: str) -> Optional[List[str]]:
    """Split on `separator` at legal points only, or None if none are legal."""
    parts = text.split(separator)
    if len(parts) < 2:
        return None

    pieces: List[str] = []
    current = parts[0]
    for nxt in parts[1:]:
        candidate_left = current
        if _split_is_legal(candidate_left, nxt):
            pieces.append(current + (separator.rstrip() if separator.strip() else ""))
            current = nxt
        else:
            # illegal break - keep the two halves together and carry on
            current = current + separator + nxt
    pieces.append(current)

    pieces = [p.strip() for p in pieces if p.strip()]
    return pieces if len(pieces) > 1 else None


def split_body(text: str, max_chars: int = MAX_CHARS) -> List[str]:
    """Recursively section-aware split, never cutting a numeric condition."""
    if len(text) <= max_chars:
        return [text]

    for separator in SEPARATORS:
        pieces = _split_once(text, separator)
        if not pieces:
            continue
        out: List[str] = []
        for piece in pieces:
            # descend only for pieces that are still too long
            out.extend(split_body(piece, max_chars) if len(piece) > max_chars else [piece])
        if len(out) > 1:
            return out

    # No legal split exists. Leaving it whole is the right call: an over-long
    # chunk loses its tail to truncation, but a chunk cut mid-rule states a
    # number the source never stated. Callers surface this as a warning.
    return [text]


def build_chunk_documents(documents: List[SourceDocument],
                          max_chars: int = MAX_CHARS) -> List[ChunkDoc]:
    """Turn loaded documents into embedding-ready chunks."""
    chunks: List[ChunkDoc] = []

    for doc in documents:
        header = _header(doc)
        body = f"Keywords: {doc.keywords}\nFact: {doc.answer}"
        whole = f"{header}\n{body}"

        if len(whole) <= max_chars:
            bodies = [body]
        else:
            # Split the body only; the header is re-stamped onto every piece so
            # each one still names its own scheme.
            budget = max_chars - len(header) - 1
            bodies = split_body(body, max(budget, 200))

        total = len(bodies)
        for i, piece in enumerate(bodies, start=1):
            suffix = "" if total == 1 else f" (part {i} of {total})"
            chunks.append(ChunkDoc(
                chunk_id=doc.id if total == 1 else f"{doc.id}-{i}",
                text=f"{header}{suffix}\n{piece}",
                scheme=doc.scheme_code,
                topic=doc.topic,
                source_id=doc.source_id,
                source_title=doc.source_title,
                source_url=doc.source_url,
                as_on=doc.as_on,
                part_index=i,
                part_total=total,
            ))

    return chunks


def oversized(chunks: List[ChunkDoc], max_chars: int = MAX_CHARS) -> List[ChunkDoc]:
    """Chunks that had no legal split point and stayed over the limit."""
    return [c for c in chunks if len(c.text) > max_chars]
