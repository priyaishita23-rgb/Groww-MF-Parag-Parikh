"""v1 must keep running on a machine with no third-party packages installed.

This cannot be checked by looking for the packages: torch, sentence-transformers
and chromadb may well be installed on the developer's machine, in which case an
accidental module-level import would work locally and only fail for someone who
installed nothing. So the test asserts the stronger, machine-independent
invariant instead:

    importing ppfaq, and answering a question, must not load the v2 stack.

If those modules are never loaded, the code path cannot depend on them.

This is IMPLEMENTATION.md rule R5, and it is the regression guard for the lazy
imports introduced in Phases 2, 4 and 5.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEAVY = ("torch", "sentence_transformers", "chromadb", "transformers", "numpy")

# Run in a fresh interpreter: modules already imported by the rest of the suite
# would otherwise show up in sys.modules and make this meaningless.
PROBE = """
import json, sys
import ppfaq
a = ppfaq.Assistant()
a.ask("What is the expense ratio of Parag Parikh Flexi Cap Fund?")
print(json.dumps([m for m in {heavy!r} if m in sys.modules]))
"""


class ZeroInstall(unittest.TestCase):
    def _probe(self, backend: str = "tfidf"):
        env = {**os.environ, "PYTHONPATH": ROOT, "RETRIEVER_BACKEND": backend}
        result = subprocess.run(
            [sys.executable, "-c", PROBE.format(heavy=HEAVY)],
            env=env, capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout.strip())

    def test_import_and_answer_do_not_load_the_v2_stack(self):
        loaded = self._probe()
        self.assertEqual(
            loaded, [],
            msg=(
                "ppfaq loaded %s on the default backend. A v2 dependency is being "
                "imported at module level; move it inside the function that needs "
                "it (IMPLEMENTATION.md R5)." % ", ".join(loaded)
            ),
        )

    def test_config_imports_only_stdlib(self):
        env = {**os.environ, "PYTHONPATH": ROOT}
        result = subprocess.run(
            [sys.executable, "-c",
             "import json, sys; from ppfaq import config; "
             "print(json.dumps(sorted({n.split('.')[0] for n in sys.modules} "
             "- set(sys.stdlib_module_names) - {'ppfaq'})))"],
            env=env, capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        third_party = [m for m in json.loads(result.stdout) if not m.startswith("_")]
        self.assertEqual(
            third_party, [],
            msg="ppfaq.config pulled in non-stdlib modules: %s" % ", ".join(third_party),
        )

    def test_invalid_backend_fails_loudly(self):
        env = {**os.environ, "PYTHONPATH": ROOT, "RETRIEVER_BACKEND": "vectro"}
        result = subprocess.run(
            [sys.executable, "-c", "from ppfaq import config"],
            env=env, capture_output=True, text=True, cwd=ROOT,
        )
        self.assertNotEqual(result.returncode, 0,
                            msg="a misspelled backend must not fall back silently")
        self.assertIn("RETRIEVER_BACKEND", result.stderr)


if __name__ == "__main__":
    unittest.main()
