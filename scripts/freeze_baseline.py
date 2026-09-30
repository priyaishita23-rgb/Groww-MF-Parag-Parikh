"""Freeze v1's exact behaviour as a machine-checkable contract.

Runs the 40-question parity set through the assistant and records the *whole*
Answer for each one, not just the fields scripts/check_parity.py compares. The
result, tests/golden/v1_answers.json, is the baseline that the Phases 2 refactor
must not disturb by a single character.

    python scripts/freeze_baseline.py            # write the golden file
    python scripts/freeze_baseline.py --check    # compare, exit 1 on any drift

Note on `score`: it is captured here deliberately, because within one backend a
refactor must not move it at all. It is NOT comparable *across* backends — the
+0.25 scheme bias makes it a biased cosine (ARCHITECTURE.md §6.4) — so the
cross-backend diff in Phase 7 compares kind, source_url and chunk_id only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.check_parity import QUESTIONS  # noqa: E402
from ppfaq.assistant import Assistant  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "golden", "v1_answers.json")


def render() -> str:
    """The golden file's exact contents for the current code."""
    assistant = Assistant()
    rows = [{"question": q, **assistant.ask(q).to_dict()} for q in QUESTIONS]
    rows.sort(key=lambda r: r["question"])
    return json.dumps(rows, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze or verify the v1 baseline")
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed file instead of writing it")
    args = parser.parse_args()

    current = render()

    if args.check:
        if not os.path.exists(GOLDEN):
            print(f"no baseline at {GOLDEN} - run without --check first")
            return 1
        with open(GOLDEN, encoding="utf-8") as fh:
            committed = fh.read()
        if current == committed:
            print(f"baseline unchanged ({len(QUESTIONS)} questions)")
            return 0
        diff = difflib.unified_diff(
            committed.splitlines(keepends=True), current.splitlines(keepends=True),
            fromfile="committed", tofile="current", n=2,
        )
        sys.stdout.writelines(diff)
        print("\nBASELINE DRIFT - behaviour changed. If this was a refactor, it was "
              "not faithful; revert and redo.")
        return 1

    os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(current)
    print(f"wrote {GOLDEN} ({len(QUESTIONS)} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
