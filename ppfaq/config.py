"""Runtime configuration: which retrieval backend to use, and where v2 keeps its
derived files.

Imports `os` and nothing else, on purpose. This module is reachable from
`import ppfaq`, so anything heavier imported here would make torch and chromadb a
requirement of the zero-install v1 demo path (IMPLEMENTATION.md rule R5).

Select the backend with an environment variable:

    RETRIEVER_BACKEND=vector python app.py          # bash
    $env:RETRIEVER_BACKEND="vector"; python app.py  # PowerShell
"""

from __future__ import annotations

import os

# --- paths ------------------------------------------------------------------
# Resolved from the repo root the same way ppfaq/corpus.py does, so the package
# works regardless of the current working directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHUNKS_DIR = os.path.join(ROOT, "chunks")
VECTORSTORE_DIR = os.path.join(ROOT, "vectorstore")

# --- retrieval backend ------------------------------------------------------
TFIDF = "tfidf"
VECTOR = "vector"
BACKENDS = (TFIDF, VECTOR)

RETRIEVER_BACKEND = (os.environ.get("RETRIEVER_BACKEND") or TFIDF).strip().lower()

if RETRIEVER_BACKEND not in BACKENDS:
    # Fail loudly rather than silently falling back to tfidf. A typo that quietly
    # ran the wrong backend would be worst during Phase 6 calibration, where it
    # would produce a threshold measured against the backend you were not testing.
    raise ValueError(
        f"RETRIEVER_BACKEND={os.environ.get('RETRIEVER_BACKEND')!r} is not valid; "
        f"expected one of {', '.join(BACKENDS)}"
    )

# --- embeddings (v2 only; unused while RETRIEVER_BACKEND == 'tfidf') ---------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
CHROMA_COLLECTION = "mf_facts"


# --- .env ------------------------------------------------------------------
def _load_dotenv(path: str) -> None:
    """Read KEY=value lines into os.environ, stdlib only.

    python-dotenv would be a dependency, and this module must stay importable
    on a machine with nothing installed (rule R5). A real environment variable
    always wins, so `GENERATION=on python app.py` overrides the file.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name, value = name.strip(), value.strip().strip('"').strip("'")
                if name and name not in os.environ:
                    os.environ[name] = value
    except OSError:
        pass  # no .env is normal; generation is off by default anyway


_load_dotenv(os.path.join(ROOT, ".env"))


def _flag(name: str, default: str = "off") -> bool:
    return (os.environ.get(name) or default).strip().lower() in ("on", "1", "true", "yes")


# --- generation (opt-in; off by default) ------------------------------------
# Off unless asked for. With generation off the assistant returns the sentence
# stored in the corpus, which is the behaviour every test and both parity
# gates are written against, and the reason a citation cannot drift from its
# answer (ARCHITECTURE §4.1).
GENERATION = _flag("GENERATION", "off")

LLM_PROVIDER = (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or "gemini-3.8-flash").strip()

# Temperature 0: this assistant quotes published figures. There is nothing for
# sampling to improve here and plenty for it to corrupt.
try:
    TEMPERATURE = float(os.environ.get("TEMPERATURE") or 0.0)
except ValueError:
    TEMPERATURE = 0.0
# 1024, not the 256 you would expect for a three-sentence answer. Gemini 3.x
# flash is a thinking model and this budget covers its internal reasoning as
# well as the reply: at 256 it spent 242 tokens thinking, left 10 for the
# answer, and returned a truncated fragment with finishReason MAX_TOKENS.
try:
    MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS") or 1024)
except ValueError:
    MAX_OUTPUT_TOKENS = 1024
