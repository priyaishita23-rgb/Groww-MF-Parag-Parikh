"""Behaviour tests. Run with:  python -m unittest discover -s tests -v"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq.assistant import Assistant  # noqa: E402


class FactRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Assistant()

    def test_expense_ratio_flexi_cap(self):
        ans = self.a.ask("What is the expense ratio of Parag Parikh Flexi Cap Fund?")
        self.assertEqual(ans.kind, "fact")
        self.assertEqual(ans.chunk_id, "C01")
        self.assertIn("1.05%", ans.text)

    def test_expense_ratio_elss_not_confused_with_flexi(self):
        ans = self.a.ask("ELSS tax saver expense ratio")
        self.assertEqual(ans.scheme, "PPTSF")
        self.assertIn("1.54%", ans.text)

    def test_elss_lock_in(self):
        ans = self.a.ask("What is the lock-in for the ELSS fund?")
        self.assertEqual(ans.topic, "lock_in")
        self.assertIn("3 years", ans.text)

    def test_exit_load_liquid_fund(self):
        ans = self.a.ask("Exit load on Parag Parikh Liquid Fund?")
        self.assertEqual(ans.scheme, "PPLF")
        self.assertEqual(ans.topic, "exit_load")

    def test_minimum_sip(self):
        ans = self.a.ask("Minimum SIP amount for the flexi cap fund")
        self.assertEqual(ans.topic, "min_sip")
        self.assertIn("1,000", ans.text)

    def test_riskometer(self):
        ans = self.a.ask("Riskometer of Parag Parikh Conservative Hybrid Fund")
        self.assertEqual(ans.topic, "riskometer")
        self.assertIn("Moderately High", ans.text)

    def test_benchmark_is_a_fact_not_a_performance_question(self):
        ans = self.a.ask("What is the benchmark of the flexi cap fund?")
        self.assertEqual(ans.kind, "fact")
        self.assertIn("NIFTY 500", ans.text)

    def test_capital_gains_statement(self):
        ans = self.a.ask("How do I download my capital gains statement?")
        self.assertEqual(ans.topic, "capital_gains_statement")

    def test_every_answer_has_one_citation(self):
        questions = [
            "expense ratio of flexi cap", "should I buy this fund?",
            "my PAN is ABCDE1234F", "what were the 3 year returns?",
            "what is the capital of France?", "",
        ]
        for q in questions:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertTrue(ans.source_url.startswith("https://"), ans.source_url)
                self.assertTrue(ans.source_title)

    def test_answers_are_at_most_three_sentences(self):
        # Split on sentence-final punctuation followed by a capitalised word, so
        # that "Rs. 1,000" and "0.53%" are not mistaken for sentence breaks.
        import re
        for chunk in self.a.chunks:
            with self.subTest(chunk=chunk.id):
                sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", chunk.answer) if s.strip()]
                self.assertLessEqual(len(sentences), 3, chunk.answer)


class Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Assistant()

    def test_refuses_buy_sell_advice(self):
        for q in ["Should I buy Parag Parikh Flexi Cap Fund?",
                  "Is the ELSS fund a good investment?",
                  "Which is better, flexi cap or ELSS?",
                  "How much should I invest in this?"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:advice")

    def test_refuses_performance(self):
        for q in ["What were the 5 year returns of the flexi cap fund?",
                  "Did it beat the benchmark?",
                  "What is the CAGR of the liquid fund?"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:performance")

    def test_refuses_pii(self):
        for q in ["My PAN is ABCDE1234F, what is my exit load?",
                  "My aadhaar is 1234 5678 9012",
                  "Call me on 9876543210",
                  "email me at someone@example.com",
                  "folio number 12345678"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "refusal:pii")

    def test_pii_refusal_mentions_nothing_stored(self):
        ans = self.a.ask("My PAN is ABCDE1234F")
        self.assertIn("stored", ans.text)

    def test_out_of_scope(self):
        for q in ["What is the capital of France?", "who won the world cup"]:
            with self.subTest(q=q):
                self.assertEqual(self.a.ask(q).kind, "no_answer")

    def test_asks_which_scheme_instead_of_guessing(self):
        for q in ["expense ratio", "what is the exit load", "min sip"]:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertEqual(ans.kind, "clarify")
                self.assertIn("Flexi Cap", ans.text)

    def test_nav_and_aum_are_pointed_at_the_factsheet_not_quoted(self):
        for q in ["daily NAV of the flexi cap fund", "what is the AUM"]:
            with self.subTest(q=q):
                ans = self.a.ask(q)
                self.assertEqual(ans.kind, "fact")
                self.assertIn("factsheet", ans.source_url)


class CorpusIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Assistant()

    def test_every_chunk_source_is_registered(self):
        for chunk in self.a.chunks:
            with self.subTest(chunk=chunk.id):
                self.assertIn(chunk.source_id, self.a.sources)

    def test_chunk_url_matches_registered_source_url(self):
        for chunk in self.a.chunks:
            with self.subTest(chunk=chunk.id):
                self.assertEqual(chunk.source_url, self.a.sources[chunk.source_id]["url"])

    def test_source_count_within_brief(self):
        self.assertGreaterEqual(len(self.a.sources), 15)
        self.assertLessEqual(len(self.a.sources), 25)

    def test_chunk_ids_unique(self):
        ids = [c.id for c in self.a.chunks]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
