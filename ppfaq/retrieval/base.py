"""The retrieval seam.

`assistant.py` depends on exactly two operations — work out which scheme a
question names, and return ranked candidate chunks. ARCHITECTURE.md §11 calls
this the seam that lets the v2 vector backend drop in without touching
orchestration, guards, the Answer contract or the UI. This module turns that
observation into an enforced interface.

Anything implementing `BaseRetriever` is substitutable. Nothing else about the
system needs to know which backend is in use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ..corpus import Chunk


@dataclass(frozen=True)
class Hit:
    """A candidate chunk and its ranking score.

    `score` is a *biased* similarity, not a raw cosine: the backend adds the
    scheme bias described in ARCHITECTURE.md §6.4, so it can exceed 1.0 and is
    not comparable across backends. It is a ranking quantity, compared against
    one fixed floor. Do not show it to a user as a confidence.
    """

    chunk: Chunk
    score: float
    #: The similarity before the scheme bias was added. Ranking uses `score`;
    #: this is kept so calibration can ask whether the *unbiased* similarity
    #: separates in-scope questions from out-of-scope ones, which the biased
    #: score cannot (a named scheme adds +0.25 to everything).
    raw: Optional[float] = None


class BaseRetriever(ABC):
    """Contract every retrieval backend must satisfy."""

    @abstractmethod
    def detect_schemes(self, question: str) -> List[str]:
        """Scheme codes named in the question, ordered by where they appear.

        Position order is what lets a multi-scheme question answer for the first
        one mentioned and offer the rest as a follow-up (PRD FR-15).
        """

    @abstractmethod
    def search(self, question: str, scheme: Optional[str] = None,
               k: int = 3) -> List[Hit]:
        """Top `k` candidates, best first.

        When `scheme` is given it is a **hard filter**, not a hint: chunks
        belonging to other schemes must not be returned at all. This is what
        makes cross-scheme contamination structurally impossible rather than
        merely unlikely (PRD FR-13, ARCHITECTURE.md §6.3).
        """
