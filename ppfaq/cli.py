"""Command-line interface.

    python -m ppfaq.cli                        # interactive
    python -m ppfaq.cli "ELSS lock-in?"        # one-shot
"""

from __future__ import annotations

import sys

from .assistant import DISCLAIMER, EXAMPLES, WELCOME, Assistant


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    assistant = Assistant()

    if argv:
        print(assistant.ask(" ".join(argv)).render())
        return 0

    print(WELCOME)
    print(DISCLAIMER)
    print("\nTry:")
    for example in EXAMPLES:
        print(f"  - {example}")
    print("\n(blank line or Ctrl+C to quit)\n")

    while True:
        try:
            question = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            return 0
        print()
        print(assistant.ask(question).render())
        print()


if __name__ == "__main__":
    raise SystemExit(main())
