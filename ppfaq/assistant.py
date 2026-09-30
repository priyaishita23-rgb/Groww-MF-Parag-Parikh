"""The assistant: guard -> retrieve -> answer with exactly one citation.

Every path out of `Assistant.ask` returns an Answer carrying a link, because the
UI contract is "one clear citation link in every answer" - including refusals,
which cite an educational or scope page instead of a fact page.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional

from . import guards
from .corpus import load_chunks, load_meta, load_schemes, load_sources
from .retrieval import BaseRetriever, get_retriever

# Below this cosine score the top hit is treated as "not in my sources".
MIN_SCORE = 0.24

DISCLAIMER = (
    "Facts-only assistant. No investment advice. Figures are quoted from public "
    "AMC/SEBI/AMFI documents and can change - always confirm on the linked source."
)

WELCOME = (
    "Hi - I answer factual questions about five Parag Parikh (PPFAS) mutual fund "
    "schemes, and every answer comes with its official source link."
)

EXAMPLES = [
    "What is the expense ratio of Parag Parikh Flexi Cap Fund?",
    "What is the lock-in for the ELSS Tax Saver Fund?",
    "What is the exit load on Parag Parikh Liquid Fund?",
]


@dataclass
class Answer:
    text: str
    source_title: str
    source_url: str
    as_on: Optional[str]
    kind: str                      # "fact" | "refusal:advice" | "refusal:pii" |
                                   # "refusal:performance" | "no_answer"
    scheme: Optional[str] = None
    topic: Optional[str] = None
    chunk_id: Optional[str] = None
    score: Optional[float] = None
    followup: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def render(self) -> str:
        """Plain-text rendering used by the CLI and the sample Q&A file."""
        lines = [self.text]
        if self.followup:
            lines.append(self.followup)
        if self.as_on:
            lines.append(f"Last updated from sources: {self.as_on}")
        lines.append(f"Source: {self.source_title} - {self.source_url}")
        return "\n".join(lines)


class Assistant:
    def __init__(self, retriever: Optional[BaseRetriever] = None,
                 backend: Optional[str] = None) -> None:
        self.chunks = load_chunks()
        self.schemes = load_schemes()
        self.sources = load_sources()
        self.meta = load_meta()
        # `retriever` injects an instance directly; `backend` names one to build.
        # Both exist for tests, which run the same assertions across backends
        # without touching the environment.
        self.retriever = retriever or get_retriever(self.chunks, self.schemes, backend)

    # -- public ------------------------------------------------------------
    def ask(self, question: str) -> Answer:
        question = (question or "").strip()
        if not question:
            return self._no_answer("Ask me about a scheme's expense ratio, exit load, "
                                   "lock-in, minimum SIP, riskometer or benchmark.")

        refusal = guards.check(question)
        if refusal:
            return Answer(
                text=refusal.message,
                source_title=refusal.link_title,
                source_url=refusal.link_url,
                as_on=None,
                kind=f"refusal:{refusal.kind}",
            )

        # A question about another fund house is in-domain in wording but out
        # of scope in fact, and it scores high enough that no relevance floor
        # can catch it (scripts/calibrate.py). Settle it before retrieval.
        house = guards.other_amc(question)
        if house:
            return self._no_answer(
                f"I don't cover {house} funds. My sources are the public documents "
                f"for five PPFAS schemes: {', '.join(self.scheme_names())}."
            )

        detected = self.retriever.detect_schemes(question)
        scheme = detected[0] if detected else None
        hits = self.retriever.search(question, scheme=scheme, k=3)

        if not hits or hits[0].score < MIN_SCORE:
            return self._no_answer(
                "I don't have that in my sources. I cover expense ratio, exit and entry "
                "load, lock-in, minimum investment and SIP, riskometer, benchmark, scheme "
                "category, inception date, fund managers and how to download statements, "
                "for five PPFAS schemes."
            )

        top = hits[0]

        # The fact exists but differs scheme by scheme and the user named none of
        # them - guessing would put a confident wrong number on screen.
        if not detected and top.chunk.scheme != "ALL":
            return Answer(
                text=(
                    f"That figure differs by scheme, so tell me which one you mean: "
                    f"{', '.join(self.scheme_names())}."
                ),
                source_title=guards.SCOPE_LINK[0],
                source_url=guards.SCOPE_LINK[1],
                as_on=None,
                kind="clarify",
                topic=top.chunk.topic,
            )

        followup = None
        if len(detected) > 1:
            others = ", ".join(self.schemes[c].name for c in detected[1:])
            followup = f"Ask the same question for {others} to see its figure."

        return Answer(
            text=top.chunk.answer,
            source_title=top.chunk.source_title,
            source_url=top.chunk.source_url,
            as_on=top.chunk.as_on,
            kind="fact",
            scheme=top.chunk.scheme,
            topic=top.chunk.topic,
            chunk_id=top.chunk.id,
            score=round(top.score, 4),
            followup=followup,
        )

    def scheme_names(self) -> List[str]:
        return [s.name for s in self.schemes.values()]

    # -- internal ----------------------------------------------------------
    def _no_answer(self, text: str) -> Answer:
        return Answer(
            text=text,
            source_title=guards.SCOPE_LINK[0],
            source_url=guards.SCOPE_LINK[1],
            as_on=None,
            kind="no_answer",
        )
