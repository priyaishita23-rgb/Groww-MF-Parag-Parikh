"""Inspect what retrieval does with a question, stage by stage.

    python scripts/try_retrieval.py "exit load on the liquid fund"
    python scripts/try_retrieval.py                       # interactive
    python scripts/try_retrieval.py -b both "TER of PPFCF"   # compare backends
    python scripts/try_retrieval.py -k 8 "minimum sip"

The CLI shows the answer. This shows the reasoning: which guard fired, which
scheme was detected, which chunks came back and with what score, where the
relevance floor fell, and why the assistant ended up saying what it said.

Useful when an answer looks wrong and you need to know whether the fault is in
scheme detection, in ranking, or in the floor - three different fixes.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq import guards  # noqa: E402
from ppfaq.assistant import MIN_SCORE, Assistant  # noqa: E402
from ppfaq.corpus import load_chunks, load_schemes  # noqa: E402
from ppfaq.retrieval import get_retriever  # noqa: E402

RULE = "-" * 74


def inspect(question: str, backend: str, k: int) -> None:
    print("=" * 74)
    print("BACKEND: %s        question: %r" % (backend, question))
    print("=" * 74)

    chunks, schemes = load_chunks(), load_schemes()

    # -- stage 1: guards, before retrieval ever runs -----------------------
    refusal = guards.check(question)
    print("1. guards          ", end="")
    if refusal:
        print("STOPPED -> refusal:%s" % refusal.kind)
        print("   %s" % refusal.message[:68])
        print("   link: %s" % refusal.link_url)
        print("\n   retrieval never ran.")
        return
    print("passed")

    house = guards.other_amc(question)
    print("2. scope           ", end="")
    if house:
        print("STOPPED -> names %r, another fund house" % house)
        print("\n   retrieval never ran.")
        return
    print("passed")

    # -- stage 2: scheme detection ----------------------------------------
    try:
        retriever = get_retriever(chunks, schemes, backend)
    except Exception as exc:
        print("\n   backend unavailable: %s" % str(exc).splitlines()[0])
        return

    detected = retriever.detect_schemes(question)
    scheme = detected[0] if detected else None
    print("3. scheme detect   %s" % (
        ", ".join("%s (%s)" % (c, schemes[c].name) for c in detected)
        if detected else "none named - generic chunks preferred, and a "
                         "scheme-specific top hit will trigger a clarify"))
    if scheme:
        print("   hard filter -> only %s and ALL chunks are scored" % scheme)

    # -- stage 3: ranked candidates ---------------------------------------
    hits = retriever.search(question, scheme=scheme, k=k)
    print("4. retrieve        top %d of %d chunks" % (len(hits), len(chunks)))
    print()
    print("   %-6s %-8s %-24s %8s %8s" % ("id", "scheme", "topic", "score", "raw"))
    print("   " + RULE)
    for i, hit in enumerate(hits):
        raw = "%8.4f" % hit.raw if hit.raw is not None else "       -"
        mark = "  <- chosen" if i == 0 else ""
        print("   %-6s %-8s %-24s %8.4f %s%s"
              % (hit.chunk.id, hit.chunk.scheme, hit.chunk.topic,
                 hit.score, raw, mark))
    if not hits:
        print("   (nothing scored above zero)")
    print()

    # -- stage 4: the floor, and what the assistant concludes --------------
    top = hits[0].score if hits else 0.0
    print("5. floor           %.4f vs MIN_SCORE %.2f -> %s"
          % (top, MIN_SCORE, "above, answer" if top >= MIN_SCORE else
             "below, 'not in my sources'"))

    answer = Assistant(backend=backend).ask(question)
    print("6. answer          kind=%s  chunk=%s  generated=%s"
          % (answer.kind, answer.chunk_id, answer.generated))
    print()
    print("   %s" % answer.text[:220])
    if answer.followup:
        print("   %s" % answer.followup)
    if answer.as_on:
        print("   Last updated from sources: %s" % answer.as_on)
    print("   Source: %s" % answer.source_url)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show what retrieval does with a question")
    parser.add_argument("question", nargs="*", help="the question to trace")
    parser.add_argument("-b", "--backend", default="tfidf",
                        choices=["tfidf", "vector", "both"])
    parser.add_argument("-k", type=int, default=5, help="candidates to show")
    args = parser.parse_args()

    backends = ["tfidf", "vector"] if args.backend == "both" else [args.backend]

    if args.question:
        for backend in backends:
            inspect(" ".join(args.question), backend, args.k)
        return 0

    print("Type a question, or blank to quit.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        for backend in backends:
            inspect(question, backend, args.k)


if __name__ == "__main__":
    raise SystemExit(main())
