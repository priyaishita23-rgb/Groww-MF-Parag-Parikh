"""Build dist/index.html - a single self-contained page with the corpus inlined.

This is the hosted demo. It runs the same retrieval and the same guards as the
Python service, over the same corpus files, so the two cannot answer differently
as long as the corpus is the single source of truth.

    python scripts/build_standalone.py
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq.assistant import DISCLAIMER, EXAMPLES, MIN_SCORE, WELCOME  # noqa: E402
from ppfaq.corpus import load_sources  # noqa: E402

TEMPLATE = os.path.join(ROOT, "web", "standalone.template.html")
OUT = os.path.join(ROOT, "dist", "index.html")


def main() -> None:
    with open(os.path.join(ROOT, "corpus", "corpus.json"), encoding="utf-8") as fh:
        corpus = json.load(fh)
    with open(os.path.join(ROOT, "corpus", "schemes.json"), encoding="utf-8") as fh:
        scope = json.load(fh)
    copy = {
        "welcome": WELCOME,
        "disclaimer": DISCLAIMER,
        "examples": EXAMPLES,
        "source_count": len(load_sources()),
    }

    with open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()

    def inject(marker: str, value) -> None:
        nonlocal html
        pattern = re.compile(re.escape(f"/*__{marker}__*/") + r"\s*[^;]+;")
        replacement = f"/*__{marker}__*/ {json.dumps(value, ensure_ascii=False)};"
        html, count = pattern.subn(lambda _: replacement, html, count=1)
        if count != 1:
            raise SystemExit(f"marker __{marker}__ not found in template")

    inject("CORPUS", corpus)
    inject("SCOPE", scope)
    inject("COPY", copy)
    inject("MIN_SCORE", MIN_SCORE)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {OUT} ({len(html)/1024:.1f} KB, {len(corpus)} facts)")


if __name__ == "__main__":
    main()
