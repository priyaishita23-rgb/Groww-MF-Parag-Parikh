"""Phase 2B/2C — the Load and Chunk stages of the v2 pipeline.

The splitter is never triggered by the real corpus (the longest chunk is well
under MAX_CHARS), so the numeric-condition rule is exercised here against
synthetic input. That is deliberate: the rule exists to stop a regression in
data that has not been written yet, not to fix today's corpus.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq.chunking import (  # noqa: E402
    MAX_CHARS, _OPENS_CONDITION, build_chunk_documents, split_body,
)
from ppfaq.corpus import load_chunks  # noqa: E402
from ppfaq.pipeline.load import (  # noqa: E402
    ProvenanceError, _validate, load_documents,
)
from ppfaq.corpus import load_schemes, load_sources  # noqa: E402


class Loading(unittest.TestCase):
    def setUp(self):
        self.docs = load_documents()

    def test_loads_every_corpus_record(self):
        self.assertEqual(len(self.docs), len(load_chunks()))

    def test_every_document_carries_resolved_provenance(self):
        for d in self.docs:
            self.assertTrue(d.source_id, msg=d.id)
            self.assertTrue(d.source_url.startswith("http"), msg=d.id)
            self.assertTrue(d.publisher, msg="%s has no publisher" % d.id)
            self.assertTrue(d.as_on, msg=d.id)

    def test_scheme_resolved_or_explicitly_all(self):
        for d in self.docs:
            if d.scheme_code == "ALL":
                self.assertIsNone(d.scheme, msg=d.id)
                self.assertFalse(d.is_scheme_specific, msg=d.id)
            else:
                self.assertIsNotNone(d.scheme, msg=d.id)
                self.assertEqual(d.scheme.code, d.scheme_code, msg=d.id)

    def test_unregistered_source_id_raises(self):
        chunks = load_chunks()
        broken = replace(chunks[0], source_id="S99")
        with self.assertRaises(ProvenanceError) as ctx:
            _validate([broken], load_sources(), load_schemes())
        self.assertIn(broken.id, str(ctx.exception))
        self.assertIn("S99", str(ctx.exception))

    def test_source_url_mismatch_raises(self):
        chunks = load_chunks()
        broken = replace(chunks[0], source_url="https://example.com/not-the-source")
        with self.assertRaises(ProvenanceError) as ctx:
            _validate([broken], load_sources(), load_schemes())
        self.assertIn("does not match the register", str(ctx.exception))

    def test_all_problems_reported_not_just_the_first(self):
        chunks = load_chunks()
        broken = [
            replace(chunks[0], source_id="S98"),
            replace(chunks[1], source_id="S99"),
        ]
        with self.assertRaises(ProvenanceError) as ctx:
            _validate(broken, load_sources(), load_schemes())
        message = str(ctx.exception)
        self.assertIn(broken[0].id, message)
        self.assertIn(broken[1].id, message)
        self.assertIn("2 provenance problem", message)


class Chunking(unittest.TestCase):
    def setUp(self):
        self.chunks = build_chunk_documents(load_documents())

    def test_every_corpus_record_is_represented(self):
        ids = {c.chunk_id.split("-")[0] for c in self.chunks}
        self.assertEqual(ids, {c.id for c in load_chunks()})

    def test_every_chunk_names_its_scheme(self):
        for c in self.chunks:
            self.assertTrue(c.text.startswith("Scheme: "), msg=c.chunk_id)

    def test_every_chunk_carries_citation_metadata(self):
        for c in self.chunks:
            self.assertTrue(c.source_url.startswith("http"), msg=c.chunk_id)
            self.assertTrue(c.as_on, msg=c.chunk_id)
            self.assertTrue(c.source_id, msg=c.chunk_id)

    def test_chunk_ids_unique(self):
        ids = [c.chunk_id for c in self.chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_graded_exit_load_ladder_is_not_torn(self):
        """The PPLF day-1-to-6 ladder must arrive as one chunk."""
        pplf = [c for c in self.chunks
                if c.scheme == "PPLF" and c.topic == "exit_load"]
        self.assertEqual(len(pplf), 1, msg="the ladder was split across chunks")
        text = pplf[0].text
        for rate in ("0.0070%", "0.0065%", "0.0060%",
                     "0.0055%", "0.0050%", "0.0045%"):
            self.assertIn(rate, text, msg="%s missing from the ladder" % rate)

    def test_real_corpus_needs_no_splitting(self):
        """Documents this short should pass through whole.

        If this starts failing, the corpus has grown a long record and the
        splitter is now load-bearing - go and read the new chunks.txt.
        """
        for c in self.chunks:
            self.assertEqual(c.part_total, 1, msg=c.chunk_id)
            self.assertLessEqual(len(c.text), MAX_CHARS, msg=c.chunk_id)


class NumericConditionRule(unittest.TestCase):
    """A split must never strand a number from the condition qualifying it."""

    #: Commas placed so that a naive ", " split would leave "if redeemed ..."
    #: orphaned from the rate it qualifies.
    LADDER = " ".join(
        "Exit load of 0.00%02d%%, if redeemed within %d days from the date of "
        "allotment of the respective units, calculated on a first in first out "
        "basis across the folio." % (70 - i * 5, i + 1)
        for i in range(14)
    )

    def test_synthetic_ladder_never_splits_mid_condition(self):
        self.assertGreater(len(self.LADDER), 2000)
        pieces = split_body(self.LADDER, max_chars=300)
        self.assertGreater(len(pieces), 1, msg="expected the splitter to run")
        for piece in pieces:
            self.assertIsNone(
                _OPENS_CONDITION.match(piece),
                msg="piece begins with a dangling condition: %r" % piece[:80],
            )

    def test_no_piece_ends_on_a_bare_rate(self):
        for piece in split_body(self.LADDER, max_chars=300):
            self.assertFalse(
                piece.rstrip().endswith("%"),
                msg="piece ends on a rate with its condition cut off: %r" % piece[-80:],
            )

    def test_unsplittable_text_is_left_whole_rather_than_cut(self):
        """No legal split point means keep it intact and let the caller warn."""
        text = "Exit load of 0.0070%, if redeemed within 1 day " * 40
        pieces = split_body(text, max_chars=100)
        for piece in pieces:
            self.assertIsNone(_OPENS_CONDITION.match(piece))

    def test_ordinary_prose_still_splits(self):
        text = ("The scheme invests in equity and equity related instruments. " * 30)
        pieces = split_body(text, max_chars=300)
        self.assertGreater(len(pieces), 1)


class Fingerprints(unittest.TestCase):
    """Staleness detection (Phase 4). Stdlib only - no torch, no chromadb."""

    def setUp(self):
        from ppfaq.pipeline import fingerprint
        self.fp = fingerprint
        if not os.path.exists(fingerprint.MANIFEST):
            self.skipTest("no chunks/manifest.json - run scripts/build_chunks.py")

    def test_corpus_fingerprint_is_stable(self):
        self.assertEqual(self.fp.corpus_fingerprint(), self.fp.corpus_fingerprint())
        self.assertEqual(len(self.fp.corpus_fingerprint()), 64)

    def test_corpus_and_chunks_fingerprints_differ(self):
        self.assertNotEqual(self.fp.corpus_fingerprint(), self.fp.chunks_fingerprint())

    def test_manifest_matches_the_corpus_on_disk(self):
        manifest = self.fp.read_manifest()
        self.assertEqual(manifest["corpus_fingerprint"], self.fp.corpus_fingerprint(),
                         msg="chunks are stale - run scripts/build_chunks.py")

    def test_require_fresh_chunks_passes_when_current(self):
        self.assertIsNotNone(self.fp.require_fresh_chunks())

    def test_stale_corpus_fingerprint_raises(self):
        import json as _json
        with open(self.fp.MANIFEST, encoding="utf-8") as fh:
            original = fh.read()
        try:
            data = _json.loads(original)
            data["corpus_fingerprint"] = "0" * 64
            with open(self.fp.MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
                _json.dump(data, fh, indent=2)
            with self.assertRaises(self.fp.StaleChunksError) as ctx:
                self.fp.require_fresh_chunks()
            self.assertIn("build_chunks.py", str(ctx.exception))
        finally:
            with open(self.fp.MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(original)

    def test_hash_ignores_line_endings(self):
        """A CRLF checkout must not invalidate a good vector store.

        Git rewrites line endings on checkout, so hashing raw bytes meant a
        fresh clone on Windows rejected a perfectly valid store as stale. The
        corpus is identical either way; only the bytes differ.
        """
        import tempfile
        lf = b"line one\nline two\n"
        crlf = b"line one\r\nline two\r\n"
        digests = []
        for content in (lf, crlf):
            directory = tempfile.mkdtemp()
            path = os.path.join(directory, "same.json")
            with open(path, "wb") as fh:
                fh.write(content)
            digests.append(self.fp._sha256([path]))
        self.assertEqual(digests[0], digests[1],
                         msg="line endings changed the fingerprint")

    def test_manifest_records_the_embedding_model(self):
        from ppfaq import config
        manifest = self.fp.read_manifest()
        self.assertEqual(manifest["embedding_model"], config.EMBEDDING_MODEL)
        self.assertEqual(manifest["embedding_dim"], config.EMBEDDING_DIM)


if __name__ == "__main__":
    unittest.main()
