"""The v2 acceptance gate (PRD TR-6): does the vector backend answer like v1?

    python scripts/check_parity_v2.py
    python scripts/check_parity_v2.py --verbose

Runs the 40-question parity set through both backends and diffs each answer
against tests/golden/v1_answers.json on **kind, source_url and chunk_id**.

`score` is deliberately excluded. The scheme bias makes it a biased cosine on
one backend and a biased TF-IDF cosine on the other (ARCHITECTURE §6.4), so
comparing it would fail on all 40 questions while telling us nothing.

Exit code 0 only when both backends match the baseline on every question. A
divergence is not automatically a bug - a v2 answer can be different and still
defensible - but TR-6 as written requires the same chunk, so anything that
differs has to be looked at and decided on, not waved through.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq.assistant import Assistant  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "golden", "v1_answers.json")
COMPARED = ("kind", "source_url", "chunk_id")


def load_golden():
    with open(GOLDEN, encoding="utf-8") as fh:
        return {row["question"]: row for row in json.load(fh)}


def run(backend: str, questions):
    assistant = Assistant(backend=backend)
    return {q: assistant.ask(q).to_dict() for q in questions}


def diff(golden, actual, questions):
    out = []
    for question in questions:
        expected, got = golden[question], actual[question]
        fields = [f for f in COMPARED if expected.get(f) != got.get(f)]
        if fields:
            out.append((question, expected, got, fields))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="v1 vs v2 parity gate")
    parser.add_argument("--verbose", action="store_true",
                        help="print every question, not just divergences")
    args = parser.parse_args()

    if not os.path.exists(GOLDEN):
        print("no baseline - run: python scripts/freeze_baseline.py")
        return 1

    golden = load_golden()
    questions = sorted(golden)

    results = {}
    for backend in ("tfidf", "vector"):
        try:
            results[backend] = run(backend, questions)
        except Exception as exc:
            print("%s backend unavailable: %s" % (backend, str(exc).splitlines()[0]))
            return 1

    failed = False
    for backend in ("tfidf", "vector"):
        divergences = diff(golden, results[backend], questions)
        matched = len(questions) - len(divergences)
        print("=" * 76)
        print("%s vs golden baseline: %d/%d match on %s"
              % (backend, matched, len(questions), ", ".join(COMPARED)))
        print("=" * 76)

        if divergences:
            failed = True
            print("%-42s %-22s %-22s" % ("question", "v1 (golden)", backend))
            print("-" * 76)
            for question, expected, got, fields in divergences:
                print("%-42s %-22s %-22s"
                      % (question[:42],
                         "%s/%s" % (expected["kind"], expected["chunk_id"]),
                         "%s/%s" % (got["kind"], got["chunk_id"])))
                print("%-42s   differs on: %s" % ("", ", ".join(fields)))
        else:
            print("no divergences")
        print()

        if args.verbose:
            for question in questions:
                got = results[backend][question]
                print("  %-46s %s/%s" % (question[:46], got["kind"], got["chunk_id"]))
            print()

    print("=" * 76)
    print("RESULT: %s" % ("PARITY" if not failed else
                          "DIVERGENCE - decide each case, do not widen the gate"))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
