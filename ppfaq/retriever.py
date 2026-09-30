"""Deprecated import path — retrieval moved to `ppfaq.retrieval` in Phase 2.

Kept so that `from ppfaq.retriever import Retriever` still resolves. New code
should import from `ppfaq.retrieval`:

    from ppfaq.retrieval import get_retriever, TfidfRetriever, Hit, tokenize
"""

from __future__ import annotations

from .retrieval.base import BaseRetriever, Hit
from .retrieval.schemes import detect_schemes
from .retrieval.tfidf import TfidfRetriever, tokenize

#: Historical name for the TF-IDF backend.
Retriever = TfidfRetriever

__all__ = [
    "BaseRetriever", "Hit", "Retriever", "TfidfRetriever",
    "detect_schemes", "tokenize",
]
