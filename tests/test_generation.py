"""The grounding check on generated answers (Phase 9).

All offline: verify() is a pure function, so the cases that matter can be
tested without spending a call or depending on the network.

These assertions are the whole reason generation is allowed to exist here. A
fluent wrong number under an official-looking citation is the worst output
this product can produce, and the only thing standing between the model and
that outcome is this function.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq import config, generate  # noqa: E402
from ppfaq.assistant import Assistant  # noqa: E402

SOURCE = (
    "Parag Parikh Flexi Cap Fund's base expense ratio is 1.05% for the Regular "
    "Plan and 0.53% for the Direct Plan, as on the last business day of August "
    "2026. Base expense ratio is exclusive of GST on management fees and of "
    "other permitted add-ons; the AMC publishes the current applicable TER "
    "separately."
)


class Verification(unittest.TestCase):
    def ok(self, text, finish="STOP"):
        return generate.verify(text, SOURCE, finish)

    # -- the case the whole mechanism exists for ---------------------------
    def test_rejects_a_figure_not_in_the_source(self):
        reason = self.ok("The base expense ratio is 1.15% for the Regular Plan.")
        self.assertIsNotNone(reason, "a hallucinated figure was accepted")
        self.assertIn("1.15", reason)

    def test_rejects_a_plausible_decimal_slip(self):
        self.assertIsNotNone(self.ok("The Direct Plan expense ratio is 0.053%."))

    def test_accepts_figures_that_are_in_the_source(self):
        self.assertIsNone(self.ok(
            "The base expense ratio is 1.05% for the Regular Plan and 0.53% "
            "for the Direct Plan, as on the last business day of August 2026."))

    def test_comma_formatting_does_not_cause_a_false_rejection(self):
        source = "The minimum SIP amount is Rs. 1,000 per instalment."
        self.assertIsNone(generate.verify(
            "The minimum SIP is Rs. 1000 per instalment.", source))

    # -- truncation: fluent, numberless, and says nothing ------------------
    def test_rejects_truncation_reported_by_the_api(self):
        reason = self.ok("Parag Parikh Flexi Cap Fund's", finish="MAX_TOKENS")
        self.assertIsNotNone(reason)
        self.assertIn("truncated", reason)

    def test_rejects_text_ending_mid_sentence(self):
        self.assertIsNotNone(self.ok("The base expense ratio is"))

    # -- the other guard rails ---------------------------------------------
    def test_rejects_more_than_three_sentences(self):
        self.assertIsNotNone(self.ok("One. Two. Three. Four."))

    def test_rejects_advisory_language(self):
        self.assertIsNotNone(self.ok("You should consider this fund."))

    def test_rejects_a_model_supplied_url(self):
        self.assertIsNotNone(self.ok("See https://example.com for details."))

    def test_rejects_the_insufficient_sentinel(self):
        self.assertIsNotNone(self.ok("INSUFFICIENT"))

    def test_rejects_empty(self):
        self.assertIsNotNone(self.ok(""))
        self.assertIsNotNone(self.ok("   "))


class Wiring(unittest.TestCase):
    def test_generation_is_off_by_default(self):
        self.assertFalse(config.GENERATION,
                         msg="generation must be opt-in; the offline demo path "
                             "and every parity gate assume stored answers")
        self.assertFalse(generate.available())

    def test_answers_are_stored_not_generated_by_default(self):
        answer = Assistant().ask("What is the expense ratio of Parag Parikh "
                                 "Flexi Cap Fund?")
        self.assertFalse(answer.generated)
        self.assertIn("1.05%", answer.text)

    def test_citation_is_never_taken_from_the_model(self):
        """The Answer's link comes from the chunk, whatever the model wrote.

        This is the structural half of FR-11: the model is asked for prose
        only, so there is no code path by which it can choose a citation.
        """
        answer = Assistant().ask("Exit load on Parag Parikh Liquid Fund?")
        chunk = {c.id: c for c in Assistant().chunks}[answer.chunk_id]
        self.assertEqual(answer.source_url, chunk.source_url)
        self.assertEqual(answer.as_on, chunk.as_on)

    def test_no_api_key_is_ever_logged_in_an_answer(self):
        key = config.GEMINI_API_KEY
        if not key:
            self.skipTest("no key configured")
        for question in ["expense ratio of flexi cap", "should I buy this?",
                         "what is the capital of France?"]:
            answer = Assistant().ask(question)
            self.assertNotIn(key, answer.text)
            self.assertNotIn(key, answer.source_url)


if __name__ == "__main__":
    unittest.main()
