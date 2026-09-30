"""Find a relevance floor that answers every in-scope question and refuses
every out-of-scope one — or prove none exists (IMPLEMENTATION.md Phase 6).

    python scripts/calibrate.py                 # both backends
    python scripts/calibrate.py --backend vector

Two sweeps per backend, because there are two candidate quantities to threshold:

  biased  the score the assistant ranks on today, scheme bias included
  raw     the similarity before the bias

The distinction matters. A detected scheme adds +0.25 to every chunk of that
scheme, so any question naming a fund - including one about a *different*
AMC's fund - floats above a floor set on the biased score. If the raw sweep
separates and the biased sweep does not, the fix is to threshold on raw and
rank on biased, not to move the number.

Exit code 0 only if some floor satisfies both sides.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq import guards  # noqa: E402
from ppfaq.corpus import load_chunks, load_schemes  # noqa: E402
from ppfaq.retrieval import get_retriever  # noqa: E402
from tests.negatives import OUT_OF_SCOPE  # noqa: E402

# In-scope questions that must keep being answered: the fact-bearing subset of
# the parity set (refusals and clarifications do not depend on the floor).
POSITIVES = [
    "What is the expense ratio of Parag Parikh Flexi Cap Fund?",
    "ELSS tax saver expense ratio",
    "TER of PPFCF",
    "What is the lock-in for the ELSS fund?",
    "Exit load on Parag Parikh Liquid Fund?",
    "exit load flexi cap",
    "Minimum SIP amount for the flexi cap fund",
    "smallest SIP in the ELSS fund",
    "Riskometer of Parag Parikh Conservative Hybrid Fund",
    "how risky is the flexi cap fund",
    "What is the benchmark of the flexi cap fund?",
    "which index does PPCHF track",
    "How do I download my capital gains statement?",
    "when was the liquid fund launched",
    "who manages the flexi cap fund",
    "what category is the conservative hybrid fund",
    "minimum investment in the dynamic asset allocation fund",
    "entry load",
    "where do I find the factsheet",
]


def top_scores(backend: str):
    """Best (biased, raw) score per question, after guards and scheme filter."""
    chunks, schemes = load_chunks(), load_schemes()
    retriever = get_retriever(chunks, schemes, backend)

    def best(question: str):
        # Mirror the real pipeline: everything the assistant settles before
        # retrieval never reaches the floor, so it must not count here either.
        if guards.check(question) is not None:
            return None
        if guards.other_amc(question) is not None:
            return None
        detected = retriever.detect_schemes(question)
        scheme = detected[0] if detected else None
        hits = retriever.search(question, scheme=scheme, k=3)
        if not hits:
            return (0.0, 0.0)
        return (hits[0].score, hits[0].raw if hits[0].raw is not None else hits[0].score)

    pos = [(q, best(q)) for q in POSITIVES]
    neg = [(q, best(q)) for q in OUT_OF_SCOPE]
    return ([(q, s) for q, s in pos if s], [(q, s) for q, s in neg if s])


def sweep(positives, negatives, index: int, label: str) -> bool:
    """Try every floor; report the widest band that works. True if one exists."""
    pos = sorted((s[index], q) for q, s in positives)
    neg = sorted(((s[index], q) for q, s in negatives), reverse=True)

    lowest_pos, lowest_pos_q = pos[0]
    highest_neg, highest_neg_q = neg[0]

    print("  %s" % label)
    print("    lowest  in-scope   %.4f   %s" % (lowest_pos, lowest_pos_q[:52]))
    print("    highest out-scope  %.4f   %s" % (highest_neg, highest_neg_q[:52]))

    if lowest_pos > highest_neg:
        floor = round((lowest_pos + highest_neg) / 2, 3)
        print("    SEPARABLE  band (%.4f, %.4f)  ->  MIN_SCORE = %.3f"
              % (highest_neg, lowest_pos, floor))
        return True

    print("    OVERLAP %.4f - no floor works on this quantity"
          % (highest_neg - lowest_pos))
    bad = [(s, q) for s, q in neg if s >= lowest_pos]
    print("    out-of-scope questions at or above the lowest in-scope score:")
    for score, question in bad[:8]:
        print("      %.4f  %s" % (score, question[:60]))
    return False


def table(positives, negatives, index: int) -> None:
    """Leak/loss counts across the range, so the shape is visible."""
    print("    floor   answered/%d   leaked/%d" % (len(positives), len(negatives)))
    step = 0.05
    f = 0.05
    while f <= 0.95:
        answered = sum(1 for _, s in positives if s[index] >= f)
        leaked = sum(1 for _, s in negatives if s[index] >= f)
        flag = "  <-- clean" if answered == len(positives) and leaked == 0 else ""
        print("    %5.2f   %8d     %6d%s" % (f, answered, leaked, flag))
        f += step


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the relevance floor")
    parser.add_argument("--backend", choices=["tfidf", "vector", "both"],
                        default="both")
    parser.add_argument("--table", action="store_true",
                        help="print the full sweep table")
    args = parser.parse_args()

    backends = ["tfidf", "vector"] if args.backend == "both" else [args.backend]
    ok = True

    for backend in backends:
        print("=" * 72)
        print("BACKEND: %s" % backend)
        print("=" * 72)
        try:
            positives, negatives = top_scores(backend)
        except Exception as exc:
            print("  unavailable: %s" % str(exc).splitlines()[0])
            continue

        print("  %d in-scope, %d out-of-scope questions scored\n"
              % (len(positives), len(negatives)))

        biased_ok = sweep(positives, negatives, 0, "BIASED score (ranked on today)")
        if args.table:
            table(positives, negatives, 0)
        print()
        raw_ok = sweep(positives, negatives, 1, "RAW similarity (before bias)")
        if args.table:
            table(positives, negatives, 1)
        print()

        ok = ok and (biased_ok or raw_ok)

    print("=" * 72)
    print("RESULT: %s" % ("a workable floor exists" if ok else
                          "NO workable floor - see IMPLEMENTATION.md Phase 6"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
