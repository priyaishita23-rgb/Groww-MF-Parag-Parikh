"""Questions the assistant must refuse to answer, and the tests that enforce it.

Two separate guardrails are covered here, and they fail in different ways.

**Out of scope** - the question is legitimate but the corpus has no answer.
The assistant must say so rather than return its nearest chunk. Under v1 two
mechanisms stop these: the relevance floor, and FR-17's max-IDF rule, which
gives an unseen word the weight of the rarest term so an off-topic query is
actively pushed down. **v2 loses the second one** - a dense model returns a
plausible neighbour for any input whatsoever - so the floor is the only
defence left, and it has to be measured rather than guessed
(scripts/calibrate.py).

**Refusals** - PII, advice and performance. These run before retrieval and are
deterministic (ARCHITECTURE §7), so both backends must behave identically. A
difference here is a wiring bug, not a tuning problem.

The vector cases are skipped when the store or its dependencies are absent, so
the suite still runs on a machine with nothing installed.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq.assistant import Assistant  # noqa: E402

# --- out of scope: must reach "I don't have that in my sources" -------------
OUT_OF_SCOPE = [
    # plainly unrelated
    "What is the capital of France?",
    "who won the world cup",
    "how do I cook pasta",
    "what is the weather tomorrow",
    "tell me a joke",
    # nonsense
    "asdfgh qwerty zxcvb",
    "?????",
    "12345 67890",
    # another AMC's funds - the dangerous ones, they look in-domain
    "expense ratio of the HDFC Small Cap Fund",
    "what is the exit load on SBI Bluechip Fund",
    "minimum SIP for Axis Midcap",
    "lock-in for the ICICI ELSS fund",
    # plausible MF facts this corpus does not hold
    "what is the portfolio turnover ratio",
    "who is the custodian of the scheme",
    "what is the trustee company's registered office",
    "what is the ISIN of the flexi cap fund",
    "how many stocks are in the portfolio",
    "what is the cash holding percentage",
    "who is the registrar and transfer agent",
    "what is the modified duration of the liquid fund",
    "what is the yield to maturity",
    "what is the standard deviation of the fund",
    # off-domain finance
    "what is the entry load on a fixed deposit",
    "does this fund invest in cryptocurrency",
    "what is the interest rate on a PPF account",
    "how do I open a demat account",
    "what is the GST rate on brokerage",
]

# --- deterministic refusals: identical on every backend ---------------------
PII = [
    "My PAN is ABCDE1234F, what is my lock-in?",
    "Call me on 9876543210",
    "my aadhaar is 1234 5678 9012",
    "email me at someone@example.com",
    "my folio number is 12345678",
    "the OTP is 448122",
]

ADVICE = [
    "Should I buy Parag Parikh Flexi Cap?",
    "which is better, the ELSS or the flexi cap?",
    "is this a good investment",
    "do you recommend this fund",
    "what should I do with my portfolio",
    "is the liquid fund safe for me",
]

PERFORMANCE = [
    "what were the 5-year returns",
    "what is the CAGR of the flexi cap fund",
    "did it beat the benchmark",
    "how has this fund performed",
    "what is the XIRR",
]


def _vector_available() -> bool:
    """True when the vector backend can actually be constructed."""
    try:
        from ppfaq.corpus import load_chunks, load_schemes
        from ppfaq.retrieval.vector import VectorRetriever
        VectorRetriever(load_chunks(), load_schemes())
        return True
    except Exception:
        return False


VECTOR_OK = _vector_available()
skip_vector = unittest.skipUnless(
    VECTOR_OK, "vector store or its dependencies unavailable")


class _GuardrailContract:
    """Assertions both backends must satisfy. Subclasses set `backend`."""

    backend = "tfidf"

    @classmethod
    def setUpClass(cls):
        cls.assistant = Assistant(backend=cls.backend)

    def test_out_of_scope_is_refused(self):
        leaked = []
        for question in OUT_OF_SCOPE:
            answer = self.assistant.ask(question)
            if answer.kind not in ("no_answer", "clarify"):
                leaked.append((question, answer.kind, answer.chunk_id, answer.score))
        self.assertEqual(
            leaked, [],
            msg="%d/%d out-of-scope questions were answered on the %s backend:\n%s"
                % (len(leaked), len(OUT_OF_SCOPE), self.backend,
                   "\n".join("  %-46s -> %s %s (%.3f)"
                             % (q[:46], k, c, s or 0) for q, k, c, s in leaked)),
        )

    def test_pii_is_refused(self):
        for question in PII:
            self.assertEqual(self.assistant.ask(question).kind, "refusal:pii",
                             msg=question)

    def test_advice_is_refused(self):
        for question in ADVICE:
            self.assertEqual(self.assistant.ask(question).kind, "refusal:advice",
                             msg=question)

    def test_performance_is_refused(self):
        for question in PERFORMANCE:
            self.assertEqual(self.assistant.ask(question).kind,
                             "refusal:performance", msg=question)

    def test_every_refusal_still_carries_a_link(self):
        for question in PII + ADVICE + PERFORMANCE + OUT_OF_SCOPE:
            answer = self.assistant.ask(question)
            self.assertTrue(answer.source_url.startswith("http"), msg=question)


class GuardrailsTfidf(_GuardrailContract, unittest.TestCase):
    backend = "tfidf"


@skip_vector
class GuardrailsVector(_GuardrailContract, unittest.TestCase):
    backend = "vector"


if __name__ == "__main__":
    unittest.main()
