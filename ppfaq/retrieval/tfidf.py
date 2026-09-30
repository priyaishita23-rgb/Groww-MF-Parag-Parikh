"""TF-IDF retrieval over the fact corpus — the v1 backend, stdlib only.

The corpus is tiny and every chunk is already a single fact, so a dense vector
store would be overkill. What actually decides accuracy here is *scheme
disambiguation*: "exit load of the liquid fund" and "exit load of the ELSS" must
not collide. So scheme detection runs first and hard-filters the candidates,
and TF-IDF only picks the topic within that scheme.

Moved from ppfaq/retriever.py in Phase 2. The scoring, bias constants,
tokenisation, stopwords and synonyms are unchanged — this backend's behaviour is
frozen by tests/golden/v1_answers.json.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional

from ..corpus import Chunk, Scheme
from .base import BaseRetriever, Hit
from .schemes import detect_schemes as _detect_schemes

_TOKEN = re.compile(r"[a-z0-9]+")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "its", "me", "much", "my", "of", "on", "or", "please",
    "tell", "that", "the", "their", "there", "this", "to", "was", "what", "whats", "when",
    "where", "which", "who", "will", "with", "you", "your", "fund", "scheme", "parag",
    "parikh", "ppfas", "mutual",
}

# short forms users type that should map onto corpus vocabulary
_SYNONYMS = {
    "ter": ["expense", "ratio"],
    "er": ["expense", "ratio"],
    "charges": ["expense", "ratio"],
    "fee": ["expense", "ratio"],
    "fees": ["expense", "ratio"],
    "cost": ["expense", "ratio"],
    "lockin": ["lock", "in"],
    "locked": ["lock", "in"],
    "sip": ["sip", "minimum"],
    "riskometer": ["riskometer", "risk"],
    "cg": ["capital", "gains"],
    "statement": ["statement"],
    "download": ["download", "statement"],
    "manager": ["manager"],
    "managers": ["manager"],
    "index": ["benchmark"],
    "started": ["inception"],
    "launch": ["inception"],
    "launched": ["inception"],
    "old": ["inception"],
    "redeem": ["exit", "load"],
    "redemption": ["exit", "load"],
    "withdraw": ["exit", "load"],
}


def tokenize(text: str) -> List[str]:
    out: List[str] = []
    for tok in _TOKEN.findall((text or "").lower()):
        if tok in _SYNONYMS:
            out.extend(_SYNONYMS[tok])
        if tok in _STOPWORDS or len(tok) < 2:
            continue
        out.append(tok)
    return out


class TfidfRetriever(BaseRetriever):
    """TF-IDF cosine with a hard scheme filter in front of it."""

    def __init__(self, chunks: List[Chunk], schemes: Dict[str, Scheme]):
        self.chunks = chunks
        self.schemes = schemes
        self._df: Counter = Counter()
        self._vectors: List[Dict[str, float]] = []
        for chunk in chunks:
            terms = set(tokenize(chunk.text))
            self._df.update(terms)
        n = len(chunks)
        self._idf = {term: math.log((n + 1) / (df + 0.5)) for term, df in self._df.items()}
        # A term the corpus has never seen is the rarest term there is. Giving it
        # the maximum idf (rather than zero) means an off-topic word such as
        # "france" takes up real mass in the query vector and pulls the cosine
        # down, instead of silently vanishing and leaving a spurious match.
        self._oov_idf = max(self._idf.values(), default=1.0)
        for chunk in chunks:
            self._vectors.append(self._vector(tokenize(chunk.text)))

    # -- vectors -----------------------------------------------------------
    def _vector(self, terms: List[str]) -> Dict[str, float]:
        tf = Counter(terms)
        vec = {t: (1 + math.log(c)) * self._idf.get(t, self._oov_idf) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    # -- scheme detection --------------------------------------------------
    def detect_schemes(self, question: str) -> List[str]:
        return _detect_schemes(question, self.schemes)

    # -- search ------------------------------------------------------------
    def search(self, question: str, scheme: Optional[str] = None, k: int = 3) -> List[Hit]:
        qvec = self._vector(tokenize(question))
        hits: List[Hit] = []
        for chunk, cvec in zip(self.chunks, self._vectors):
            if scheme is not None and chunk.scheme not in (scheme, "ALL"):
                continue
            raw = sum(w * cvec.get(t, 0.0) for t, w in qvec.items())
            score = raw
            if scheme is not None and chunk.scheme == scheme:
                score += 0.25          # prefer the named scheme over generic chunks
            elif scheme is not None and chunk.scheme == "ALL":
                score += 0.05
            elif scheme is None and chunk.scheme != "ALL":
                score -= 0.10          # ambiguous question, generic facts first
            if score > 0:
                hits.append(Hit(chunk, score, raw))
        hits.sort(key=lambda h: (-h.score, h.chunk.id))
        return hits[:k]
