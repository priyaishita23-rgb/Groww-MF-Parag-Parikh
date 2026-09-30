"""RAG stage 1 — Load.

Reads the corpus, joins each fact to its registered source row and its scheme,
and refuses to hand back anything whose provenance does not check out.

Why validate here rather than trust the files. The citation contract (PRD FR-11)
says every answer carries exactly one source link, and the whole design rests on
that link being the document the fact actually came from (ARCHITECTURE §4.1). In
v1 the corpus and the answer travel together in one record, so the pairing is
hard to break, and tests are enough. In v2 the fact goes into a vector store and
the URL rides along as metadata — a further hop, made once at ingestion and then
trusted at query time forever after. A provenance break introduced here would
surface as an official-looking link under an answer it does not support, which
is the single worst output this product can produce. So it is checked at the
boundary, and it raises.

    from ppfaq.pipeline import load_documents
    docs = load_documents()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..corpus import Chunk, Scheme, load_chunks, load_meta, load_schemes, load_sources


@dataclass(frozen=True)
class SourceDocument:
    """A corpus fact with its provenance and scheme resolved."""

    # -- the fact ----------------------------------------------------------
    id: str
    scheme_code: str            # a scheme code, or "ALL" for facts that do not vary
    topic: str
    keywords: str
    answer: str
    as_on: str

    # -- provenance, from corpus/sources.csv -------------------------------
    source_id: str
    source_title: str
    source_url: str
    publisher: str
    doc_type: str
    used_for: str

    # -- resolved scheme; None for "ALL" -----------------------------------
    scheme: Optional[Scheme]

    @property
    def scheme_name(self) -> str:
        return self.scheme.name if self.scheme else "All schemes"

    @property
    def is_scheme_specific(self) -> bool:
        return self.scheme is not None


class ProvenanceError(ValueError):
    """Raised when a fact cannot be traced to a registered source."""


def _validate(chunks: List[Chunk], sources: Dict[str, dict],
              schemes: Dict[str, Scheme]) -> None:
    """Collect every provenance problem, then raise once naming all of them.

    Reporting all failures at once matters: these are authoring errors in a
    hand-assembled corpus, and fixing them one interpreter run at a time is slow
    and invites the fixer to stop at the first.
    """
    problems: List[str] = []

    for chunk in chunks:
        row = sources.get(chunk.source_id)
        if row is None:
            problems.append(
                f"{chunk.id}: source_id {chunk.source_id!r} is not in sources.csv"
            )
            continue
        if (chunk.source_url or "").strip() != (row.get("url") or "").strip():
            problems.append(
                f"{chunk.id}: source_url does not match the register\n"
                f"      chunk:    {chunk.source_url}\n"
                f"      {chunk.source_id} says: {row.get('url')}"
            )
        if chunk.scheme != "ALL" and chunk.scheme not in schemes:
            problems.append(
                f"{chunk.id}: scheme {chunk.scheme!r} is not in schemes.json"
            )

    seen: set = set()
    for chunk in chunks:
        if chunk.id in seen:
            problems.append(f"{chunk.id}: duplicate chunk id")
        seen.add(chunk.id)

    if problems:
        raise ProvenanceError(
            "%d provenance problem(s) in the corpus:\n  - %s"
            % (len(problems), "\n  - ".join(problems))
        )


def load_documents() -> List[SourceDocument]:
    """Load the corpus and return facts with provenance and scheme resolved."""
    chunks = load_chunks()
    sources = load_sources()
    schemes = load_schemes()

    _validate(chunks, sources, schemes)

    documents: List[SourceDocument] = []
    for chunk in chunks:
        row = sources[chunk.source_id]
        documents.append(SourceDocument(
            id=chunk.id,
            scheme_code=chunk.scheme,
            topic=chunk.topic,
            keywords=chunk.keywords,
            answer=chunk.answer,
            as_on=chunk.as_on,
            source_id=chunk.source_id,
            source_title=chunk.source_title,
            source_url=chunk.source_url,
            publisher=row.get("publisher", ""),
            doc_type=row.get("doc_type", ""),
            used_for=row.get("used_for", ""),
            scheme=schemes.get(chunk.scheme),
        ))
    return documents


def describe_documents(documents: List[SourceDocument]) -> str:
    """A readable stage-1 report: what was loaded, and where it came from."""
    meta = load_meta()
    schemes = load_schemes()
    sources = load_sources()

    topics = sorted({d.topic for d in documents})
    order = [c for c in schemes] + ["ALL"]

    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("RAG STAGE 1 - LOAD")
    lines.append("=" * 78)
    lines.append(f"AMC                 {meta.get('amc')}")
    lines.append(f"Corpus last updated {meta.get('corpus_last_updated')}")
    lines.append(f"Factsheet as on     {meta.get('factsheet_as_on')}")
    lines.append(f"Documents loaded    {len(documents)}")
    lines.append(f"Schemes             {len(schemes)}")
    lines.append(f"Topics              {len(topics)}")
    lines.append(f"Sources registered  {len(sources)}")
    lines.append("")

    # scheme x topic grid
    width = max(len(t) for t in topics) + 2
    header = " " * width + "".join(f"{c:>8}" for c in order)
    lines.append("FACTS BY SCHEME AND TOPIC")
    lines.append(header)
    by_key = {(d.topic, d.scheme_code) for d in documents}
    for topic in topics:
        row = f"{topic:<{width}}"
        for code in order:
            row += f"{'  x' if (topic, code) in by_key else '   ':>8}"
        lines.append(row)
    lines.append("")

    # source usage
    lines.append("SOURCE REGISTER  (facts citing each source)")
    counts: Dict[str, int] = {}
    for d in documents:
        counts[d.source_id] = counts.get(d.source_id, 0) + 1
    for sid in sorted(sources):
        row = sources[sid]
        used = counts.get(sid, 0)
        mark = f"{used:>3}" if used else "  -"
        lines.append(f"  {sid}  {mark}  {row.get('publisher','')} - {row.get('title','')}")
        lines.append(f"            {row.get('url','')}")
    lines.append("")
    unused = [s for s in sources if s not in counts]
    if unused:
        lines.append(f"Registered but not cited by any fact: {', '.join(sorted(unused))}")
        lines.append("(kept in the register because the brief asks for the full source list)")
    lines.append("")
    return "\n".join(lines)
