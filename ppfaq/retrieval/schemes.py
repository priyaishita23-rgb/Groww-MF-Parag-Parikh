"""Scheme detection — exact alias matching, shared by every backend.

This deliberately does not live in a backend. Working out *which fund* a
question is about is not a similarity problem: it is a lookup against a list of
names and aliases held in corpus/schemes.json (ARCHITECTURE.md §6.3).

Both backends must use this identical implementation. That is what guarantees
v1 and v2 can never disagree about which scheme was asked about — the hard
filter they each apply downstream is then filtering on the same answer.

Under the vector backend this matters *more*, not less: MiniLM will not reliably
separate two chunks that differ only in a proper noun, so exact detection plus a
hard metadata filter is the whole defence against a wrong-fund answer.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from ..corpus import Scheme


def detect_schemes(question: str, schemes: Dict[str, Scheme]) -> List[str]:
    """Scheme codes named in `question`, ordered by position of first mention."""
    q = " " + re.sub(r"[^a-z0-9 ]+", " ", (question or "").lower()) + " "
    q = re.sub(r"\s+", " ", q)
    found: List[Tuple[int, str]] = []
    for code, scheme in schemes.items():
        for alias in [scheme.name.lower(), code.lower()] + scheme.aliases:
            pos = q.find(" " + alias.lower() + " ")
            if pos == -1 and not alias.endswith(" "):
                # allow "elss?" / "liquid," style endings
                m = re.search(r"\b" + re.escape(alias.lower()) + r"\b", q)
                pos = m.start() if m else -1
            if pos != -1:
                found.append((pos, code))
                break
    found.sort()
    ordered: List[str] = []
    for _, code in found:
        if code not in ordered:
            ordered.append(code)
    return ordered
