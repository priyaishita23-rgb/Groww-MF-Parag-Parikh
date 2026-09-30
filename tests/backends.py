"""A11-A17 run against both backends (IMPLEMENTATION.md Phase 7, step 2).

    python -m unittest tests.backends -v

Not named test_*.py, so `unittest discover` does not pick it up. That is
deliberate. The default backend is tfidf and v1 is the shipped product; the
discovered suite reports v1's health and stays honest at green. This module is
the v2 gate, run explicitly, and it is expected to fail while the vector
backend diverges. Making it pass by relaxing an assertion would defeat its only
purpose (standing rule R7).

The guard tests (A11-A14) must pass on both backends unconditionally: guards
run before retrieval and never touch it, so a difference there is a wiring bug,
not a tuning question. The routing tests (A15-A17) depend on retrieval and are
where real divergence shows up.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq.assistant import Assistant  # noqa: E402


def _vector_available() -> bool:
    try:
        from ppfaq.corpus import load_chunks, load_schemes
        from ppfaq.retrieval.vector import VectorRetriever
        VectorRetriever(load_chunks(), load_schemes())
        return True
    except Exception:
        return False


VECTOR_OK = _vector_available()


class _BackendContract:
    """Subclasses set `backend`."""

    backend = "tfidf"

    @classmethod
    def setUpClass(cls):
        cls.a = Assistant(backend=cls.backend)

    # -- A11-A14: guards. Identical on every backend, no exceptions. --------
    def test_a11_refuses_buy_sell_advice(self):
        for q in ["Should I buy Parag Parikh Flexi Cap Fund?",
                  "Is the ELSS fund a good investment?",
                  "Which is better, flexi cap or ELSS?",
                  "How much should I invest in this?"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:advice")

    def test_a12_refuses_performance(self):
        for q in ["What were the 5 year returns of the flexi cap fund?",
                  "Did it beat the benchmark?",
                  "What is the CAGR of the liquid fund?"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:performance")

    def test_a13_refuses_pii(self):
        for q in ["My PAN is ABCDE1234F, what is my exit load?",
                  "My aadhaar is 1234 5678 9012",
                  "Call me on 9876543210",
                  "email me at someone@example.com",
                  "folio number 12345678"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:pii")

    def test_a14_pii_refusal_mentions_nothing_stored(self):
        self.assertIn("stored", self.a.ask("My PAN is ABCDE1234F").text)

    # -- A15-A17: routing. Retrieval-dependent. -----------------------------
    def test_a15_out_of_scope(self):
        for q in ["What is the capital of France?", "who won the world cup"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "no_answer")

    def test_a16_asks_which_scheme_instead_of_guessing(self):
        for q in ["expense ratio", "what is the exit load", "min sip"]:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertEqual(ans.kind, "clarify",
                                 msg="%r was answered instead of asking which scheme "
                                     "(FR-14); got %s/%s" % (q, ans.kind, ans.chunk_id))
                self.assertIn("Flexi Cap", ans.text)

    def test_a17_nav_and_aum_point_at_the_factsheet(self):
        """FR-9: NAV/AUM deflect to the factsheet rather than quoting a figure.

        Asserting on `source_url` alone - as tests/test_assistant.py does - is
        too weak to carry this requirement. Most PPFAS facts cite the same
        factsheet PDF, so a question about NAV that wrongly returns an *exit
        load* chunk still satisfies "factsheet is in the url". This checks the
        topic as well, which is what FR-9 actually means.
        """
        for q in ["daily NAV of the flexi cap fund", "what is the AUM",
                  "what is the NAV of the ELSS fund",
                  "current NAV of the liquid fund"]:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertEqual(ans.kind, "fact")
                self.assertIn(ans.topic, ("nav", "aum"),
                              msg="%r must be deflected to the NAV/AUM chunk; got "
                                  "%s (%s) instead (FR-9)"
                                  % (q, ans.chunk_id, ans.topic))
                self.assertIn("factsheet", ans.source_url)

    # -- contract that holds regardless of backend --------------------------
    def test_every_answer_carries_one_citation(self):
        for q in ["expense ratio of flexi cap", "should I buy this fund?",
                  "my PAN is ABCDE1234F", "what were the 3 year returns?",
                  "what is the capital of France?", ""]:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertTrue(ans.source_url.startswith("https://"))
                self.assertTrue(ans.source_title)


class BackendTfidf(_BackendContract, unittest.TestCase):
    backend = "tfidf"


@unittest.skipUnless(VECTOR_OK, "vector store or dependencies unavailable")
class BackendVector(_BackendContract, unittest.TestCase):
    backend = "vector"


if __name__ == "__main__":
    unittest.main()
