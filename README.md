# MF Facts Desk — facts-only mutual fund FAQ assistant

**Product chosen (for all milestones): Groww.**
A retail investor on Groww comparing schemes gets the same repetitive questions answered
here — expense ratio, exit load, lock-in, minimum SIP, riskometer, benchmark, how to pull a
capital-gains statement — with an official source link on every single answer, and a polite
refusal for anything that would be advice.

Hosted prototype: <https://claude.ai/artifact/4u2R4F9wcFckrcLiLCSnpe>
(private link — the owner must share it before others can open it)

---

## Two projects in this repository

| Directory | Project |
|---|---|
| **root** | **MF Facts Desk** — the milestone deliverable, described in this README. A facts-only RAG FAQ assistant over PPFAS scheme documents |
| [`support-assistant/`](support-assistant/) | **Support Assistant** — a separate prototype: an interactive customer-support chat widget for an investing app, with mock domain tools and compliance guardrails |

They share a theme but nothing else — different corpora, different stacks, separate
test suites, no shared code. The milestone work is everything at the root; read
[`support-assistant/README.md`](support-assistant/README.md) for the other one.

```bash
cd support-assistant && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8080
```

---

## Scope

**AMC:** PPFAS Mutual Fund (PPFAS Asset Management Pvt. Ltd.)

**Schemes (5):**

| Code | Scheme | Category |
|---|---|---|
| PPFCF | Parag Parikh Flexi Cap Fund | Flexi cap equity |
| PPTSF | Parag Parikh ELSS Tax Saver Fund | ELSS (tax saver) |
| PPCHF | Parag Parikh Conservative Hybrid Fund | Conservative hybrid |
| PPDAAF | Parag Parikh Dynamic Asset Allocation Fund | Dynamic asset allocation |
| PPLF | Parag Parikh Liquid Fund | Liquid |

**Corpus:** 55 fact chunks drawn from **24 public pages** — PPFAS scheme pages, the monthly
factsheet, TER statutory disclosures, KIM/SID/SAI documents, the Investor Desk statement
pages, plus AMFI and SEBI pages. Full list with what each one was used for:
[`corpus/sources.csv`](corpus/sources.csv). No third-party blogs, no app back-end screens.

Figures are quoted as at the **August 2026 factsheet (as on 31 August 2026)**; the corpus was
assembled on **29 September 2026**.

---

## Run it

Python 3.9+ and **no third-party packages** — nothing to install.

```bash
python app.py
```

Then open <http://127.0.0.1:8000>.

Command line instead:

```bash
python -m ppfaq.cli "What is the exit load on Parag Parikh Liquid Fund?"
```

```bash
python -m ppfaq.cli
```

Tests:

```bash
python -m unittest discover -s tests -v
```

Regenerate the derived files after editing the corpus:

```bash
python scripts/make_samples.py && python scripts/build_standalone.py
```

Check that the hosted page still answers exactly like the Python service (needs Node):

```bash
python scripts/check_parity.py && node scripts/check_parity.mjs
```

---

## The two retrieval backends

The default backend, `tfidf`, is the one described above: no install, no network,
no API key. It is the demo path, and everything below is optional.

`vector` is the embedding pipeline the brief calls for — MiniLM + ChromaDB. It
answers from the same corpus through the same guards; only the step that decides
*which* fact to show is different.

```bash
pip install -r requirements-v2.txt
python scripts/build_chunks.py     # stage 1-2: load, chunk  -> chunks/
python scripts/ingest.py           # stage 3-4: embed, store -> vectorstore/
```

```bash
$env:RETRIEVER_BACKEND="vector"; python app.py
```

Ingestion runs once. `vectorstore/` is gitignored and rebuilt in about 20 seconds;
`scripts/ingest.py --check` reports whether it is current, and a store built from a
different corpus is refused rather than served.

Each pipeline stage writes something readable, so it can be shown rather than
described:

| Stage | Command | Output |
|---|---|---|
| 1 · Load | `scripts/build_chunks.py` | `chunks/documents.txt` |
| 2 · Chunk | `scripts/build_chunks.py` | `chunks/chunks.txt` — all 55 chunks |
| 3 · Embed | `scripts/export_embeddings.py` | `chunks/embeddings.txt` — 55 × 384 vectors |
| 4 · Store | `scripts/ingest.py` | `vectorstore/` |

**`vector` is not yet at parity with `tfidf`** — 39 of 44 questions agree. See
[Known limits](#known-limits).

---

## Optional: generated answers

Off by default. With generation off, an answer *is* the sentence stored in the
corpus, which is what makes it impossible for a citation to drift from the text
above it.

```bash
cp .env.example .env     # then add GEMINI_API_KEY
```

```bash
$env:GENERATION="on"; python app.py
```

Two things keep this from costing the citation contract. The model is never given
the chance to choose a source: it receives one retrieved chunk, is asked for prose,
and the title, URL and date are attached afterwards from that chunk. And every
number it writes must already appear in that chunk — a decimal slip or an invented
lock-in is caught and the stored sentence used instead, silently.

`.env` is gitignored. Put real keys there and nowhere else; a key pushed to a public
repo is compromised immediately, and deleting it later does not remove it from the
history.

---

## What runs where

| | `tfidf` | `vector` | generation |
|---|---|---|---|
| `python app.py` (local) | default | opt-in | opt-in |
| `python -m ppfaq.cli` | default | opt-in | opt-in |
| `dist/index.html` (hosted) | **only** | no | no |

**The hosted page is v1 only.** It is a JavaScript port that runs entirely in the
browser, so it can neither load MiniLM nor hold an API key. It answers from the same
corpus with the same guards and the same stored sentences — but if you open the
hosted link expecting to see the embedding pipeline or a generated answer, you will
not. Run it locally for those.

---

## How it works

```
question
   │
   ├─ 1. guards        PII → advice → performance              (ppfaq/guards.py)
   │                   any hit stops here with a polite refusal + an educational link
   │
   ├─ 2. scope         names another fund house? → "not in my sources"
   │                   no relevance floor can catch these; see Known limits
   │
   ├─ 3. scheme detect  "liquid fund" → PPLF            (ppfaq/retrieval/schemes.py)
   │                   hard-filters candidates so schemes can't be confused
   │                   shared by both backends, so they cannot disagree
   │
   ├─ 4. retrieve      TF-IDF cosine, or MiniLM + ChromaDB     (ppfaq/retrieval/)
   │                   below the floor → "not in my sources"
   │                   no scheme named but the fact differs by scheme → ask which
   │
   └─ 5. answer        the chunk's stored ≤3-sentence fact
                       (optionally rephrased, then checked)   (ppfaq/generate.py)
                       + "Last updated from sources: …"
                       + exactly one citation link, taken from the chunk
```

Two deliberate choices are worth calling out.

**Answers are written into the corpus, not generated.** Each chunk holds the finished
sentence and the URL it came from, so an answer cannot drift from its citation. Retrieval
picks *which* fact to show; it never paraphrases one.

**An unseen word counts as the rarest word, not a free one.** The usual TF-IDF default gives
out-of-vocabulary terms zero weight, so *"What is the capital of France?"* collapses to
`capital` and matches the capital-gains chunk with false confidence. Giving unknown terms the
maximum IDF makes `france` take up real mass in the query vector and pushes the score below
threshold, which is what routes genuinely off-topic questions to the fallback.

### Refusals

| Trigger | Example | Link returned |
|---|---|---|
| PII | "My PAN is ABCDE1234F…", "my folio number is 12345678" | PPFAS scheme list |
| Opinion / portfolio | "Should I buy this?", "Is the liquid fund safe for me?" | AMFI — Risks in mutual funds |
| Performance | "5-year returns?", "Did it beat the benchmark?" | PPFAS factsheet archive |
| Another fund house | "lock-in for the ICICI ELSS fund" | PPFAS scheme list |

Every refusal still carries a link, because the UI contract is one citation on *every* answer.

The last row exists because of a measurement, not a hunch. *"lock-in for the ICICI
ELSS fund"* scored **higher than most legitimate questions** — "elss" matches a scheme
alias, retrieval narrows to the PPFAS ELSS, and the scheme bias lifts it. No relevance
floor could ever reject it, so scope is decided before retrieval runs.

---

## Constraints, and how each is met

- **Public sources only** — every chunk's `source_id` resolves to a row in `corpus/sources.csv`;
  a test enforces it, and a second test checks the chunk's URL matches the registered one.
- **No PII** — questions are answered and discarded. The server logs nothing, writes nothing,
  and keeps no session; the hosted page runs entirely in the browser with no network calls at
  all. PAN, Aadhaar, phone, email, folio and OTP patterns are refused before retrieval runs.
- **No performance claims** — returns are never computed or compared. NAV and AUM questions
  are answered by pointing at the official factsheet rather than by quoting a number.
- **Clarity** — a test asserts every corpus answer is at most three sentences, and every
  fact answer carries `Last updated from sources: <date>`.

---

## Layout

```
app.py                      stdlib HTTP server + JSON API
ppfaq/
  guards.py                 PII / advice / performance / other-AMC refusals
  assistant.py              orchestration, thresholds, answer shape
  config.py                 backend + generation switches, .env loading
  cli.py                    terminal interface
  retrieval/
    base.py                 the Hit + BaseRetriever seam
    schemes.py              alias matching, shared by both backends
    tfidf.py                v1 backend, stdlib only
    vector.py               v2 backend, MiniLM + ChromaDB
  pipeline/
    load.py                 stage 1, resolves and enforces provenance
    fingerprint.py          detects a stale index before it answers
  chunking.py               stage 2, recursive section-aware
  embedding.py              stage 3, MiniLM, lazily imported
  generate.py               optional generation + its grounding check
corpus/
  corpus.json               55 fact chunks, each with its source
  schemes.json              AMC + scheme scope and aliases
  sources.csv               the 24 URLs, with what each was used for
chunks/                     generated: documents.txt, chunks.txt, embeddings.txt
vectorstore/                generated, gitignored: the ChromaDB collection
web/
  index.html                UI for the local server
  standalone.template.html  hosted single-page build (JS port of the same logic)
dist/index.html             built hosted page (generated)
docs/
  sample-qa.md              12 worked queries (generated)
  disclaimer.md             the disclaimer snippet used in the UI
  calibration.txt           the threshold sweep behind the Known limits
scripts/                    build, ingest, export, and the verification gates
tests/                      61 tests, plus two gates run explicitly
```

`tests/negatives.py` and `tests/backends.py` are deliberately not named `test_*.py`,
so `unittest discover` skips them. The discovered suite covers the default backend
and stays green; those two are explicit gates that currently fail on `vector`, and
relaxing them to pass would defeat their purpose.

---

## Known limits
<a id="known-limits"></a>

- **The `vector` backend is not at parity with `tfidf`.** 39 of 44 parity questions
  agree (`python scripts/check_parity_v2.py`). The five that differ are all cases
  where v2 is worse, and three trace to the same cause: MiniLM does not know that
  "TER" means expense ratio, "index" means benchmark or "launched" means inception,
  where the TF-IDF backend has a hand-built synonym map that does. `tfidf` remains
  the default and the demo path for that reason.
- **No relevance floor separates in-scope from out-of-scope questions**, on either
  backend (`python scripts/calibrate.py`, table in `docs/calibration.txt`). The
  out-of-AMC guard closed the largest category; what remains is questions asking
  about a topic the corpus does not hold while naming a fund it does — ISIN, modified
  duration, custodian, portfolio turnover. Those still return a nearest fact rather
  than a refusal: 2 of 27 on `tfidf`, 6 of 27 on `vector`. `MIN_SCORE_VECTOR` has
  deliberately **not** been tuned to hide this.
- **`fund_managers` is missing for three schemes.** PPFCF and PPLF have it; PPTSF,
  PPCHF and PPDAAF do not, so "who manages the Conservative Hybrid Fund?" falls
  through to the fallback.
- **The corpus is hand-assembled, and no raw source is captured.** `sources.csv`
  lists all 24 URLs and every fact resolves to one, enforced at load time — but the
  repo holds no copy of the pages themselves, so provenance is traceable rather than
  evidenced. There is no scraper by design: every number was read from a document so
  it could be traced.
- **Eight of the 24 registered sources are not cited by any fact** (S11–S15, S17,
  S23, S24). S23 is used directly by the advice refusal; the rest are KIM/SID/SAI
  PDFs kept in the register because the brief asks for the full source list. Sixteen
  sources are actually quoted.


- **Figures go stale.** TER changes through the month and riskometers are re-rated monthly.
  The corpus is a snapshot of the August 2026 factsheet; refresh it from the linked sources
  and bump `corpus_last_updated` in `corpus/schemes.json`. There is no scraper — the corpus
  was assembled by hand precisely so that every number could be traced to a document.
- **No paraphrasing.** A question phrased far from the corpus vocabulary falls through to the
  "not in my sources" fallback rather than being answered loosely. That is the intended
  failure mode here, but it does cost recall.
- **Retrieval is lexical.** TF-IDF has no synonym knowledge beyond the small hand-built map in
  `ppfaq/retriever.py`; "charges", "TER" and "expense ratio" are mapped, but a genuinely novel
  phrasing will not be.
- **One citation per answer, by design.** Where a fact appears in both the factsheet and the
  KIM, only the source actually used is cited.
- **Two implementations.** The hosted page is a JavaScript port of the Python logic over the
  same corpus files. `scripts/check_parity.*` guards the pair across 44 questions, but a change
  to one still has to be mirrored in the other.
- **Coverage is narrow on purpose.** Five schemes, one AMC. Taxation, NAV history, portfolio
  holdings and anything requiring a login are out of scope.
