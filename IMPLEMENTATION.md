# Implementation plan — v2 embedding pipeline

Phase-by-phase build guide for an AI coding agent (Cursor), implementing
[`ARCHITECTURE.md`](ARCHITECTURE.md) §11 against the requirements in
[`PRD.md`](PRD.md) §7.2.

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 30 September 2026 |
| **Implements** | ARCHITECTURE §11 (TR-1…TR-6) |
| **Baseline** | v1, shipped and passing 21 tests + 40-question parity |

> **This is the plan as written, kept as a record.** Counts inside the phases (21
> tests, 40 parity questions) were true when it was written and are left alone; the
> suite is now 61 tests and 44 parity questions.
>
> **Where it ended up, 30 September 2026:**
>
> | Phase | Outcome |
> |---|---|
> | 0, 1, 2A | done — baseline frozen, seam extracted, no behaviour change |
> | 2B, 2C | done — load and chunk, with provenance enforced at load time |
> | 4, 5 | done — MiniLM + ChromaDB, hard scheme filter preserved |
> | 6 | **stopped and reported.** No workable floor exists on either backend; `MIN_SCORE_VECTOR` deliberately unset. An out-of-AMC guard was added instead, which closed the largest leak category |
> | 6B | added, not in the original plan — the Phase 6 guards had to be mirrored into the JS port, and the parity set extended so the check could catch that class of drift at all |
> | 7 | gate built; **fails at 39/44.** All five divergences are v2 regressions, three caused by MiniLM lacking v1's synonym map |
> | 8 | done — docs reconciled, demo run sheet rehearsed, deliverables verified |
> | 9 | added — optional grounded generation, off by default |
>
> **Still open:** query-side synonym expansion (would likely fix 3 of the 5
> divergences), and a decision on FR-16 given no floor separates cleanly.

---

## What this plan does and does not cover

**v1 is already built and working.** The TF-IDF assistant, the corpus, the guards, the
UI and the hosted page all exist and pass their tests. This plan does **not** rebuild
them.

What is missing is the pipeline `Problemstatement.txt` mandates — MiniLM embeddings and
ChromaDB — recorded in PRD §7.2 as *specified, not yet built*. **This plan implements
that**, then closes the remaining milestone loose ends.

> If you actually wanted a from-scratch rebuild of v1, stop and say so — this document
> would need to be rewritten around a different starting point.

**The finish line:** `RETRIEVER_BACKEND=vector` answers all 40 parity questions
identically to v1, with no new advice or performance leakage, and v1 still runs with
zero dependencies installed.

---

## Standing rules

These apply to **every** phase. Put them in Cursor's context and keep them there.

| # | Rule | Why |
|---|---|---|
| R1 | **Do not modify `ppfaq/guards.py`.** Guards stay deterministic and stay ahead of retrieval | TR-5. Embeddings must never decide whether something is advice |
| R2 | **Do not modify `corpus/corpus.json`, `schemes.json` or `sources.csv`** | The corpus is the source of truth; v2 is a derived index (ARCH §11). Changing data would invalidate the parity baseline |
| R3 | **Do not change the `Answer` dataclass fields or `kind` values** | The UI, CLI, sample generator and JS port all read it (ARCH §8) |
| R4 | **Do not change answer text.** v2 changes *how a chunk is found*, never *what is said once found* | FR-11 holds by the stored-answer mechanism (ARCH §4.1) |
| R5 | **`import ppfaq` must never require torch or chromadb.** `ppfaq/__init__.py:6` imports `Assistant` eagerly — all vector imports must be lazy, inside functions | v1's zero-install demo path must survive |
| R6 | **Run `python -m unittest discover -s tests -v` after every phase.** The whole suite must stay green — never a lower count than the phase before (24 after Phase 1) | Regression gate |
| R7 | **Never weaken a threshold or delete a test to make something pass.** Report the failure instead | A green suite bought by lowering the bar is worse than a red one |
| R8 | **One phase per commit.** Do not start the next phase until the current one's Definition of Done is met | Keeps failures isolated and bisectable |

---

## Phase map

```
Phase 0  Baseline freeze            ──┐  no behaviour change
Phase 1  Dependencies + config      ──┘
                │
Phase 2  A  Retriever seam             no behaviour change
         B  Loading   — RAG stage 1
         C  Chunking  — RAG stage 2   (TR-1)
                │
Phase 3  ── merged into Phase 2C
                │
Phase 4  Ingestion → ChromaDB (TR-2, TR-3)
                │
Phase 5  VectorRetriever (TR-4)
                │
Phase 6  Threshold recalibration     ← highest-risk phase
                │
Phase 7  Parity gate (TR-6)
                │
Phase 8  Docs + milestone deliverables
```

Phases 0, 1 and 2A are refactors with **zero** behaviour change — if any test output
differs, something is wrong. Phases 2B–5 build the new path alongside the old, and
nothing they add is reachable from the default `tfidf` backend, so the golden baseline
must stay unchanged throughout. Phase 6 is where the real risk lives (see §Phase 6).
Phase 7 is the acceptance gate.

**Pipeline stages.** Phase 2 covers the first two stages of the RAG pipeline —
**Load** and **Chunk** — and Phase 4 the next two, **Embed** and **Store**. Each stage
writes a readable artefact so it can be inspected and shown rather than described:

| Stage | Phase | Code | Inspectable output |
|---|---|---|---|
| 1 · Load | 2B | `ppfaq/pipeline/load.py` | `chunks/documents.txt` |
| 2 · Chunk | 2C | `ppfaq/chunking.py` | `chunks/chunks.txt`, `chunks.jsonl` |
| 3 · Embed | 4 | `ppfaq/embedding.py` | ingest summary |
| 4 · Store | 4 | `scripts/ingest.py` | `vectorstore/` |
| 5 · Retrieve | 5 | `ppfaq/retrieval/vector.py` | — |

---

## Phase 0 — Baseline freeze

**Goal:** capture v1's exact behaviour as a machine-checkable contract before touching
anything, and clear the one piece of known dead code.

**Files**
- create `tests/golden/v1_answers.json`
- create `scripts/freeze_baseline.py`
- modify `ppfaq/retriever.py` (delete dead branch only)

**Do**

1. Run the existing suite and the parity check. Record that both pass. If either
   fails, **stop and report** — everything downstream assumes a green baseline.
2. Write `scripts/freeze_baseline.py`: run the 40 questions from
   `scripts/check_parity.py` through `Assistant`, serialise each full `Answer` dict,
   write to `tests/golden/v1_answers.json` sorted by question for stable diffs.
3. Delete the dead branch at `ppfaq/retriever.py:132-134` — the `if scheme is None and
   chunk.scheme not in ("ALL",): pass`. The no-scheme case is genuinely handled by the
   `−0.10` penalty at line 141 (ARCH §12). Delete the `pass` and its comment; **change
   nothing else** in `search()`.
4. Re-run tests and `freeze_baseline.py`. The golden file must be byte-identical to
   before the deletion — that is the proof the branch was dead.

**Must not:** touch scoring constants, `MIN_SCORE`, tokenisation, or guards.

**Definition of done**
- [ ] 21 tests pass, 40-question parity passes
- [ ] `tests/golden/v1_answers.json` exists with 40 entries
- [ ] Dead branch removed, golden file unchanged by the removal

```
Cursor prompt — Phase 0
Read ARCHITECTURE.md §6 and §12. Follow the standing rules in IMPLEMENTATION.md.
1. Run: python -m unittest discover -s tests -v
   Run: python scripts/check_parity.py && node scripts/check_parity.mjs
   Report results. If anything fails, stop.
2. Create scripts/freeze_baseline.py: import the QUESTIONS list from
   scripts/check_parity.py, run each through ppfaq.assistant.Assistant, and write
   every Answer.to_dict() to tests/golden/v1_answers.json, sorted by question,
   indent=2.
3. In ppfaq/retriever.py delete ONLY the dead branch at lines 132-134 (the
   `if scheme is None and chunk.scheme not in ("ALL",):` block ending in `pass`)
   and its comment. Change nothing else.
4. Re-run freeze_baseline.py and confirm the golden file is unchanged by step 3.
```

---

## Phase 1 — Dependencies and configuration

**Goal:** make the backend selectable, without v1 gaining a single dependency.

**Files**
- create `requirements.txt`, `requirements-v2.txt`, `ppfaq/config.py`
- modify `.gitignore`

**Do**

1. `requirements.txt` — a comment stating v1 needs nothing, and Python 3.9+.
2. `requirements-v2.txt`:
   ```
   sentence-transformers>=2.2
   chromadb>=0.4
   ```
3. `ppfaq/config.py`:
   ```python
   RETRIEVER_BACKEND = os.environ.get("RETRIEVER_BACKEND", "tfidf")  # "tfidf" | "vector"
   EMBEDDING_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"
   EMBEDDING_DIM     = 384
   VECTORSTORE_DIR   = <repo>/vectorstore
   CHROMA_COLLECTION = "mf_facts"
   CHUNKS_DIR        = <repo>/chunks
   ```
   Paths resolved relative to the repo root, mirroring `ppfaq/corpus.py:11`.
   **`config.py` imports only `os`** — no torch, no chromadb.
4. `.gitignore`: add `vectorstore/`, `scratch/`, keep `__pycache__/`.

**Must not:** import any third-party package anywhere reachable from
`import ppfaq`. Verify with a clean interpreter that has neither package installed.

**Definition of done**
- [ ] `RETRIEVER_BACKEND` defaults to `"tfidf"`
- [ ] `python app.py` and `python -m ppfaq.cli "…"` work with **nothing installed**
- [ ] 21 tests pass

```
Cursor prompt — Phase 1
Follow the standing rules in IMPLEMENTATION.md, especially R5.
Create requirements.txt (v1 needs no third-party packages; Python 3.9+),
requirements-v2.txt (sentence-transformers>=2.2, chromadb>=0.4), and
ppfaq/config.py with RETRIEVER_BACKEND (env var, default "tfidf"),
EMBEDDING_MODEL, EMBEDDING_DIM, VECTORSTORE_DIR, CHROMA_COLLECTION, CHUNKS_DIR.
Resolve paths from the repo root the same way ppfaq/corpus.py line 11 does.
config.py must import only `os`.
Add vectorstore/ and scratch/ to .gitignore.
Verify: python app.py still starts with no third-party packages installed.
```

---

## Phase 2 — Seam, loading and chunking

Three parts. **2A** is a pure refactor; **2B** and **2C** build the first two stages of
the RAG pipeline alongside the existing system, reachable only from the new build
script. The golden baseline must stay unchanged across all three.

| Part | Work | Status |
|---|---|---|
| 2A | Extract the retriever seam | done |
| 2B | Load — documents + provenance (RAG stage 1) | |
| 2C | Chunk — recursive section-aware (RAG stage 2, TR-1) | |

---

### Phase 2A — Extract the retriever seam

**Goal:** make the interface `assistant.py` depends on explicit, so a second backend
can drop in. **Pure refactor — zero behaviour change.**

ARCHITECTURE §11 names the seam: `assistant.py` uses only `detect_schemes()` and
`search() -> List[Hit]`. This phase turns that from an observation into a contract.

**Files**
- create `ppfaq/retrieval/__init__.py`, `base.py`, `schemes.py`
- move `ppfaq/retriever.py` → `ppfaq/retrieval/tfidf.py`
- modify `ppfaq/assistant.py`

**Do**

1. `ppfaq/retrieval/base.py` — `Hit` dataclass (moved, unchanged) and an ABC:
   ```python
   class BaseRetriever(ABC):
       @abstractmethod
       def detect_schemes(self, question: str) -> List[str]: ...
       @abstractmethod
       def search(self, question: str, scheme: Optional[str] = None,
                  k: int = 3) -> List[Hit]: ...
   ```
2. `ppfaq/retrieval/schemes.py` — move `detect_schemes` logic here as a free function
   `detect_schemes(question, schemes) -> List[str]`.
   **Scheme detection is not a retrieval-backend concern** (ARCH §6.3): it is exact
   alias matching and both backends must use the identical implementation. Sharing it
   is what guarantees v1 and v2 can never disagree about which fund is being asked
   about.
3. Move `Retriever` → `ppfaq/retrieval/tfidf.py` as `TfidfRetriever(BaseRetriever)`,
   delegating `detect_schemes` to `schemes.py`. **Scoring, bias constants,
   tokenisation, synonyms and stopwords copied verbatim.**
4. `ppfaq/retrieval/__init__.py` — a `get_retriever(chunks, schemes, backend=None)`
   factory reading `config.RETRIEVER_BACKEND`. The vector branch imports **inside the
   function** (R5) and for now raises `NotImplementedError`.
5. `assistant.py` — `Assistant.__init__` calls the factory. Accept an optional
   `retriever=` parameter for tests.
6. Keep `ppfaq/retriever.py` as a two-line shim re-exporting from the new location, so
   any existing import path still resolves.

**Must not:** change any number in the scorer. If a golden-file diff appears, the move
was not faithful — revert and redo.

**Definition of done**
- [ ] Full suite passes **unmodified**
- [ ] `python scripts/freeze_baseline.py --check` reports "baseline unchanged"
- [ ] `get_retriever()` returns `TfidfRetriever` by default
- [ ] `import ppfaq` still needs no third-party package

```
Cursor prompt — Phase 2
Read ARCHITECTURE.md §3, §6.3, §11. Follow the standing rules, especially R5 and R7.
This is a pure refactor: behaviour must not change by one character.
Create ppfaq/retrieval/ with base.py (Hit + BaseRetriever ABC with detect_schemes
and search), schemes.py (detect_schemes as a free function taking question and the
scheme dict), tfidf.py (the existing Retriever, renamed TfidfRetriever, subclassing
BaseRetriever, delegating detect_schemes to schemes.py — copy tokenisation,
synonyms, stopwords, idf, oov_idf and the +0.25/+0.05/-0.10 bias verbatim), and
__init__.py with get_retriever(chunks, schemes, backend=None) reading
config.RETRIEVER_BACKEND; the "vector" branch imports inside the function and
raises NotImplementedError for now.
Update ppfaq/assistant.py to use the factory, with an optional retriever= param.
Leave ppfaq/retriever.py as a shim re-exporting from the new location.
Verify: the full suite passes unmodified AND scripts/freeze_baseline.py --check
reports "baseline unchanged".
```

---

### Phase 2B — Loading (RAG stage 1)

**Goal:** make document loading an explicit, inspectable pipeline stage that resolves
and **enforces** provenance.

v1 loads the corpus through `ppfaq/corpus.py`, which reads the three files into
dataclasses and stops there. The link between a chunk and its registered source is
checked only in tests (ARCH §4.4). For v2 that link has to survive into the vector
store's metadata, so it is worth resolving — and validating — at load time.

**Files**
- create `ppfaq/pipeline/__init__.py`, `ppfaq/pipeline/load.py`

**Do**

1. `SourceDocument` — a corpus record joined to its registered source row:
   the chunk's fields, plus `publisher`, `doc_type` and `used_for` from
   `sources.csv`, plus the resolved `Scheme` (or `None` for `"ALL"` chunks).
2. `load_documents() -> List[SourceDocument]` — load, join, validate, return.
3. **Validation raises, it does not warn.** A chunk whose `source_id` is not in the
   register, or whose `source_url` differs from the registered one, is a provenance
   break: it would put an unearned citation under an answer (PRD FR-11). Collect
   *all* failures and raise one error listing them, rather than dying on the first.
4. `describe_documents(docs) -> str` — a readable report: totals, a scheme × topic
   grid, and the source register with how many chunks cite each row.

**Must not:** change `ppfaq/corpus.py`'s existing functions, or make `Assistant`
depend on this module. Loading for v1 stays exactly as it is.

**Definition of done**
- [ ] `load_documents()` returns 55 documents, every one carrying a registered source
- [ ] A deliberately broken `source_id` raises, naming the offending chunk
- [ ] Golden baseline unchanged; full suite green

---

### Phase 2C — Chunking (TR-1, RAG stage 2)

**Goal:** produce embedding-ready chunk documents with a recursive section-aware
splitter, and write them to a readable `.txt` for inspection.

The corpus is already atomic — one fact per record — so the splitter's job is not to
cut prose into windows. It is to (a) build the text that gets embedded, and (b) split
the handful of records long enough to risk MiniLM's 256-token truncation, **without
tearing a numeric rule apart**.

**Files**
- create `ppfaq/chunking.py`, `scripts/build_chunks.py`
- output `chunks/chunks.jsonl`, `chunks/chunks.txt`

**Do**

1. **Chunk document text.** For each `SourceDocument` from Phase 2B, build a
   self-contained block:
   ```
   Scheme: Parag Parikh Flexi Cap Fund (PPFAS Mutual Fund)
   Topic: Expense ratio
   Keywords: expense ratio ter total expense ratio cost charges fees regular direct plan
   Fact: <answer>
   ```
   The scheme name goes in **every** chunk. Under embeddings, a chunk that does not
   name its own fund is a wrong-fund answer waiting to happen — the hard filter (§6.3)
   is the primary defence, but the header is the cheap second one.

2. **Recursive section-aware split.** If a block exceeds `MAX_CHARS = 900`, split
   recursively on this separator ladder, trying each in order and only descending when
   a piece is still too long:
   ```
   ["\n\n", "\n", ". ", "; ", ", "]
   ```
   Every resulting piece is re-stamped with the full `Scheme:` / `Topic:` header, and
   gets `part_index` / `part_total` metadata.

3. **Numeric-condition protection — the critical rule.** A split must **never** land
   between a number and the condition that qualifies it. PPLF's exit load is the
   worst case:

   > *Exit load of 0.0070% if redeemed within 1 day, 0.0065% if redeemed within 2
   > days, …*

   Splitting on `", "` mid-ladder would produce a chunk reading `0.0060% if redeemed
   within 3 days` with no scheme and no context, and a retrieval hit on it would be a
   materially wrong answer. **Rule:** reject any candidate split that separates a
   `%`, a currency amount or a digit from a following `if` / `within` / `after` /
   `days` / `year` clause. If no legal split point exists, leave the block whole and
   **log a warning** rather than cutting it.

4. `chunks/chunks.txt` — human-readable, one block per chunk, separated by a rule,
   each headed with `[id] scheme · topic · source_id`. This file exists to be read; it
   is how you show a grader what was embedded.

5. `chunks/chunks.jsonl` — one JSON object per line: `chunk_id`, `text`, and metadata
   `scheme`, `topic`, `source_id`, `source_title`, `source_url`, `as_on`,
   `part_index`, `part_total`.

**Must not:** modify `corpus.json`. Chunks are derived artefacts.

6. `scripts/build_chunks.py` runs both stages — `load_documents()` then
   `build_chunk_documents()` — and writes `chunks/documents.txt` (stage 1),
   `chunks/chunks.txt` and `chunks/chunks.jsonl` (stage 2).

**Definition of done**
- [ ] `chunks.jsonl` has ≥ 55 records; every `corpus.json` id represented
- [ ] `chunks.txt` readable, every block names its scheme
- [ ] **PPLF exit-load ladder is intact in one chunk** — verify by eye
- [ ] Every chunk carries `source_url` and `as_on`
- [ ] Unit test: a synthetic 2,000-char graded-load string never splits mid-condition
- [ ] Golden baseline unchanged; full suite green

```
Cursor prompt — Phase 2B + 2C
Read ARCHITECTURE.md §4.1, §4.4 and PRD.md TR-1. Follow the standing rules, esp. R2.

2B — Loading. Create ppfaq/pipeline/load.py with a SourceDocument dataclass (the
corpus chunk's fields + publisher, doc_type, used_for from sources.csv + the
resolved Scheme or None for "ALL"), load_documents() -> List[SourceDocument] that
joins and VALIDATES (unregistered source_id, or source_url != registered url, must
raise — collect all failures into one error, do not stop at the first), and
describe_documents(docs) -> str returning a readable report. Do not change
ppfaq/corpus.py and do not make Assistant depend on this.

2C — Chunking. Create ppfaq/chunking.py with
build_chunk_documents(docs) -> List[ChunkDoc].
Each document becomes a block: "Scheme: <name> (<fund house>)\nTopic: <topic,
underscores to spaces, title case>\nKeywords: <keywords>\nFact: <answer>".
If a block exceeds MAX_CHARS=900, split recursively on the separator ladder
["\n\n", "\n", ". ", "; ", ", "], descending only when a piece is still too long,
re-stamping the Scheme/Topic header on every piece and setting part_index/part_total.
CRITICAL: never split between a number (%, currency, digit) and a following
if/within/after/days/year clause. If no legal split exists, leave the block whole and
log a warning. The Parag Parikh Liquid Fund graded exit load must stay in one piece.
Create scripts/build_chunks.py running load_documents() then
build_chunk_documents(), writing chunks/documents.txt (the stage-1 report),
chunks/chunks.jsonl (chunk_id, text, and metadata: scheme, topic, source_id,
source_title, source_url, as_on, part_index, part_total) and chunks/chunks.txt
(readable, one block per chunk, separated by a rule, headed
"[id] scheme · topic · source_id").
Add unit tests: a synthetic 2000-char graded exit-load string never splits
mid-condition, and a broken source_id raises from load_documents().
Do not modify corpus/corpus.json.
Verify: scripts/freeze_baseline.py --check still reports "baseline unchanged".
```

---

## Phase 3 — merged into Phase 2C

Chunking was originally its own phase. It now runs as **Phase 2C** above, alongside
Loading (2B), so that Phase 2 delivers the RAG pipeline's first two stages as one
unit. The phase numbers after this are unchanged, because Phases 5 and 7 are named in
code comments (`ppfaq/retrieval/__init__.py`, `tests/test_zero_install.py`,
`scripts/freeze_baseline.py`) that renumbering would silently falsify.

---

## Phase 4 — Ingestion into ChromaDB (TR-2, TR-3)

**Goal:** embed the chunks with MiniLM once and persist them, so startup does not
re-embed.

**Files**
- create `scripts/ingest.py`, `ppfaq/embedding.py`
- output `vectorstore/` (gitignored)

**Do**

1. `ppfaq/embedding.py` — lazy singleton loader:
   ```python
   def get_model():   # imports sentence_transformers INSIDE the function (R5)
   def embed(texts: List[str]) -> List[List[float]]
   ```
   Assert output dimension is 384; fail loudly if not.

2. `scripts/ingest.py`:
   - read `chunks/chunks.jsonl`
   - embed all texts in one batched `model.encode(...)` call
   - `chromadb.PersistentClient(path=VECTORSTORE_DIR)`
   - collection `mf_facts`, **cosine space** (`metadata={"hnsw:space": "cosine"}`) —
     must match the scoring in Phase 5
   - upsert `ids`, `embeddings`, `documents`, `metadatas`

3. **Corpus hash guard** (ARCH §11 mitigation). Compute a SHA-256 over
   `corpus.json` + `schemes.json` + `chunks.jsonl`, store it in collection metadata.
   On startup, a mismatch raises a clear error telling the user to re-run ingestion.
   A silently stale index is the failure mode here, and it is invisible until it gives
   a wrong answer.

4. Idempotency: skip if the hash matches, rebuild on `--force`.

5. Print a summary — chunk count, dimension, elapsed time, output path.

**Must not:** run ingestion implicitly from `Assistant.__init__`. Ingestion is an
explicit build step (TR-3).

**Definition of done**
- [ ] `python scripts/ingest.py` completes; `vectorstore/` created
- [ ] Collection count == `chunks.jsonl` line count
- [ ] Re-running without `--force` is a no-op; with `--force` rebuilds
- [ ] Editing a chunk and re-running without `--force` **errors** on hash mismatch
- [ ] `vectorstore/` is gitignored

```
Cursor prompt — Phase 4
Read ARCHITECTURE.md §11 and PRD.md TR-2, TR-3. Follow the standing rules, esp. R5.
Create ppfaq/embedding.py with a lazy singleton get_model() that imports
sentence_transformers INSIDE the function, loading config.EMBEDDING_MODEL, and
embed(texts) -> List[List[float]] asserting 384 dimensions.
Create scripts/ingest.py: read chunks/chunks.jsonl, embed all texts in one batched
call, open chromadb.PersistentClient(path=config.VECTORSTORE_DIR), get-or-create
collection config.CHROMA_COLLECTION with metadata={"hnsw:space": "cosine"}, and
upsert ids/embeddings/documents/metadatas.
Compute a SHA-256 over corpus/corpus.json + corpus/schemes.json + chunks/chunks.jsonl
and store it in the collection metadata. Skip work if the hash matches; --force
rebuilds. Print chunk count, dimension, elapsed time, output path.
Ingestion must NOT be triggered from Assistant.__init__.
```

---

## Phase 5 — VectorRetriever (TR-4)

**Goal:** a `BaseRetriever` implementation backed by Chroma, preserving the hard scheme
filter and the scoring shape.

**Files**
- create `ppfaq/retrieval/vector.py`
- modify `ppfaq/retrieval/__init__.py` (wire the factory branch)

**Do**

1. `VectorRetriever(BaseRetriever)`:
   - `__init__` opens the persisted collection, verifies the corpus hash, and **raises
     a clear error** if the store is missing or stale ("run `python scripts/ingest.py`")
   - `detect_schemes` — delegate to `retrieval/schemes.py`. **Identical to v1**, no
     embedding involvement (ARCH §6.3)

2. `search(question, scheme, k)`:
   - embed the question with the **same model** as ingestion
   - if `scheme` is not None, pass `where={"scheme": {"$in": [scheme, "ALL"]}}` —
     the hard filter, now a metadata clause. This is the whole point of TR-4: MiniLM
     will not reliably separate two chunks differing only in a fund name, so the filter
     matters **more** here than in v1
   - convert Chroma cosine distance to similarity: `similarity = 1 - distance`
   - apply the **same bias as v1**: `+0.25` named scheme, `+0.05` `"ALL"` with a scheme
     named, `−0.10` scheme-specific chunk with no scheme named
   - drop `score <= 0`, sort by `(-score, chunk_id)` for determinism
   - map results back to `Chunk` objects by id and return `List[Hit]`
   - query Chroma with `n_results` > `k` (say `k * 4`) before biasing, so the bias can
     genuinely reorder rather than just permute an already-truncated list

3. Wire the `"vector"` branch in `get_retriever()`, importing inside the function.

**Must not:** change `Hit`, touch `assistant.py`'s orchestration, or let the vector
path alter answer text.

**Definition of done**
- [ ] `RETRIEVER_BACKEND=vector python -m ppfaq.cli "expense ratio of flexi cap"` returns a correct, cited answer
- [ ] Scheme filter verified: an ELSS question never returns a PPFCF chunk
- [ ] Missing or stale `vectorstore/` gives a clear, actionable error
- [ ] Default backend still `tfidf`; full suite passes unchanged

```
Cursor prompt — Phase 5
Read ARCHITECTURE.md §6.3, §6.4, §11 and PRD.md TR-4. Follow the standing rules.
Create ppfaq/retrieval/vector.py with VectorRetriever(BaseRetriever).
__init__: open the persisted Chroma collection, verify the corpus hash from Phase 4,
raise a clear "run python scripts/ingest.py" error if missing or stale.
detect_schemes: delegate to retrieval/schemes.py — identical to v1, no embeddings.
search: embed the question with the same model as ingestion; if scheme is not None
pass where={"scheme": {"$in": [scheme, "ALL"]}}; request n_results=k*4; convert
distance to similarity as 1-distance; apply the SAME bias as TfidfRetriever
(+0.25 named scheme, +0.05 "ALL" when a scheme was named, -0.10 scheme-specific when
none named); drop score<=0; sort by (-score, chunk_id); map ids back to Chunk objects
and return List[Hit].
Wire the "vector" branch of get_retriever(), importing inside the function (R5).
Do not change Hit, assistant.py orchestration, or any answer text.
```

---

## Phase 6 — Threshold recalibration

> **This is the highest-risk phase. Do not rush it, and do not let it be "tuned until
> the tests pass".**

**Goal:** find a `MIN_SCORE` for the vector backend that keeps out-of-scope questions
out, and prove it.

**Why this is dangerous.** v1 has *two* defences against off-topic questions: the
relevance floor, and FR-17's max-IDF trick that actively pushes unknown words' scores
down (ARCH §6.5). **v2 loses the second one.** A dense model returns a plausible
nearest neighbour for *any* input — ask it the capital of France and it will happily
hand back the capital-gains chunk with a respectable cosine. Under v2 the floor is the
**only** thing standing between an off-topic question and a confidently wrong answer.

`MIN_SCORE = 0.24` is calibrated to biased TF-IDF and **will not transfer**. Assume it
is wrong until measured.

**Files**
- create `tests/negatives.py`, `scripts/calibrate.py`
- modify `ppfaq/config.py` (per-backend floor)

**Do**

1. `tests/negatives.py` — **at least 25** questions that must all fall through to
   `no_answer`. Cover:
   - unrelated factual questions (*capital of France*, *who won the World Cup*)
   - other AMCs (*expense ratio of the HDFC Small Cap Fund*)
   - plausible-but-absent MF facts (*what is the portfolio turnover ratio*,
     *who is the custodian*)
   - near-miss vocabulary (*what is the entry load on a fixed deposit*)
   - nonsense strings
2. `scripts/calibrate.py` — sweep the floor from 0.05 to 0.95 in 0.01 steps; for each,
   report positives answered (the 40-question set, must stay answered) and negatives
   leaked (must be zero). Print the table and the widest safe band.
3. Move the floor into `config.py` per backend: `MIN_SCORE_TFIDF = 0.24`,
   `MIN_SCORE_VECTOR = <measured>`. `assistant.py` selects by backend. Keep
   `MIN_SCORE` exported from `assistant.py` — `scripts/build_standalone.py:20` imports
   it and must keep working.
4. Pick the **midpoint of the widest band** where positives are fully answered and
   negatives fully rejected. Record the number and the band in `ARCHITECTURE.md` §11.

**If no such band exists** — if every floor either drops real answers or leaks
negatives — **stop and report it**. Do not pick a compromise. That result means the
vector backend cannot meet FR-16 on this corpus, which is a genuine, reportable finding
about the mandated architecture, and a more valuable thing to write up than a fudged
threshold. Options then: keep the max-IDF lexical score as a veto alongside the vector
score, or document v2 as not meeting FR-16.

**Definition of done**
- [ ] ≥ 25 negatives, all rejected at the chosen floor
- [ ] All 40 parity questions still answered
- [ ] Calibration table committed
- [ ] Chosen value and its safe band recorded in ARCHITECTURE §11
- [ ] Negatives run in CI against **both** backends

```
Cursor prompt — Phase 6
Read ARCHITECTURE.md §6.5, §6.6, §11 (the FR-17 risk row) and IMPLEMENTATION.md
Phase 6 in full. Follow the standing rules, especially R7.
Create tests/negatives.py with at least 25 out-of-scope questions that must all
return kind="no_answer": unrelated facts, other AMCs, plausible-but-absent MF facts,
near-miss vocabulary, nonsense.
Create scripts/calibrate.py sweeping the floor 0.05..0.95 step 0.01 for the vector
backend, reporting for each: how many of the 40 parity questions are still answered,
and how many negatives leak. Print a table and identify the widest band where
positives=40 and leaks=0.
Move the floor to config.py as MIN_SCORE_TFIDF=0.24 and MIN_SCORE_VECTOR=<measured
midpoint>; assistant.py selects by backend but must still export MIN_SCORE, because
scripts/build_standalone.py line 20 imports it.
If NO band satisfies both conditions, STOP and report the calibration table — do not
pick a compromise value and do not modify the negative set to make it pass.
```

---

## Phase 7 — Parity gate (TR-6)

**Goal:** prove v2 answers like v1 where it matters.

**Files**
- create `scripts/check_parity_v2.py`
- modify `tests/test_assistant.py` (parametrise over backends)

**Do**

1. `scripts/check_parity_v2.py` — run the 40 questions through both backends and diff
   against `tests/golden/v1_answers.json`. Compare **`kind`, `source_url` and
   `chunk_id`** — not `score`, which is not comparable across backends (ARCH §6.4).
2. Parametrise the guardrail and routing tests (A11–A17) to run against both backends.
   Guard behaviour must be **bit-identical**: guards run before retrieval and never
   touch it (R1), so any difference is a bug in the wiring.
3. **Acceptance:** every fact answer resolves to the same `chunk_id`; zero new advice
   or performance leakage.
4. Any divergence: write it up in a table — question, v1 chunk, v2 chunk — and judge
   each case. A v2 answer that is *different but also correct* still fails TR-6 as
   written; record it and decide explicitly rather than quietly widening the gate.

**Definition of done**
- [ ] All 40 questions produce the same `chunk_id` under both backends, or every
      divergence is documented and consciously accepted
- [ ] A11–A17 pass on both backends
- [ ] Negative set passes on both backends
- [ ] Original tests still pass on `tfidf`

```
Cursor prompt — Phase 7
Read PRD.md TR-6 and ARCHITECTURE.md §9, §6.4. Follow the standing rules.
Create scripts/check_parity_v2.py running the 40 parity questions through both the
tfidf and vector backends, diffing against tests/golden/v1_answers.json on kind,
source_url and chunk_id ONLY (not score — it is not comparable across backends).
Parametrise the guardrail and routing tests (A11-A17) in tests/test_assistant.py to
run against both backends.
Report any divergence as a table: question | v1 chunk_id | v2 chunk_id | verdict.
Do not widen the comparison to make it pass.
```

---

## Phase 8 — Documentation and milestone deliverables

**Goal:** close the loop so the repo tells the truth, and finish the outstanding
submission items.

**Do**

1. **README** — v2 setup (`pip install -r requirements-v2.txt`,
   `python scripts/build_chunks.py`, `python scripts/ingest.py`,
   `RETRIEVER_BACKEND=vector python app.py`). Keep v1's zero-install path as the
   documented demo path.
2. **PRD §7.2** — flip status from *specified, not yet built* to built; record the
   measured `MIN_SCORE_VECTOR`.
3. **ARCHITECTURE §11** — rewrite as *as built*; move the risk rows that materialised
   into §12; record the calibration band.
4. **Hosted page divergence.** The JS port cannot run MiniLM, so `dist/index.html`
   stays on v1 (ARCH §11). State this plainly in the README — a reader must not assume
   the hosted demo is the vector pipeline.
5. **Regenerate** `docs/sample-qa.md`; note which backend produced it.
6. **Rehearse the demo run sheet** (PRD §9) — still outstanding from v1. Run all nine
   questions against the running app, compare to what the sheet claims, and correct
   any mismatch. A discrepancy discovered live in front of an evaluator is the
   expensive way to find it.
7. **Deliverables check** against PRD §10 — all six present and current.

**Definition of done**
- [ ] README documents both paths and the hosted-page divergence
- [ ] PRD §7.2 and ARCHITECTURE §11/§12 reflect what was actually built
- [ ] `docs/sample-qa.md` regenerated
- [ ] Demo run sheet rehearsed end to end and corrected
- [ ] Full suite green on both backends

---

## Risk register

| Risk | Phase | Signal | Response |
|---|---|---|---|
| **No safe threshold band exists** | 6 | Calibration finds no floor with positives=40, leaks=0 | Stop. Report. Consider a lexical veto alongside the vector score, or document v2 as not meeting FR-16. **Do not compromise the value** |
| Refactor changes behaviour silently | 2A | Golden-file diff | Revert and redo; the move was not faithful |
| Provenance break reaches the vector store | 2B | `load_documents()` raises | Fix the corpus row or the register; never relax the check |
| Vector search confuses sibling schemes | 5, 7 | ELSS question returns a PPFCF chunk | The `where` filter is missing or wrong — it is a hard filter, not a hint |
| Stale index gives wrong answers invisibly | 4 | — | Corpus hash guard; fail loud on mismatch |
| v1's zero-install path breaks | 1, 2, 5 | `import ppfaq` needs torch | R5 — all vector imports lazy, inside functions |
| Graded exit load torn by the splitter | 2C | A chunk containing a bare `0.0060% if redeemed within 3 days` | Numeric-condition rule; leave whole and warn rather than cut |
| Model download fails at demo time | 8 | — | MiniLM is ~90 MB and cached on first run. Pre-warm before class; keep v1 as the offline fallback |

---

## Quick reference

```bash
# v1 — zero install
python app.py
python -m ppfaq.cli "What is the exit load on Parag Parikh Liquid Fund?"

# v2 — build once, then run
pip install -r requirements-v2.txt
python scripts/build_chunks.py          # → chunks/chunks.txt + .jsonl
python scripts/ingest.py                # → vectorstore/
RETRIEVER_BACKEND=vector python app.py

# verify
python -m unittest discover -s tests -v
python scripts/freeze_baseline.py
python scripts/check_parity.py && node scripts/check_parity.mjs
python scripts/check_parity_v2.py
python scripts/calibrate.py
```

On Windows PowerShell, set the backend with `$env:RETRIEVER_BACKEND="vector"` before
the command.
