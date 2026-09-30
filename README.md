# MF Facts Desk — facts-only mutual fund FAQ assistant

**Product chosen (for all milestones): Groww.**
A retail investor on Groww comparing schemes gets the same repetitive questions answered
here — expense ratio, exit load, lock-in, minimum SIP, riskometer, benchmark, how to pull a
capital-gains statement — with an official source link on every single answer, and a polite
refusal for anything that would be advice.

Hosted prototype: <https://claude.ai/artifact/4u2R4F9wcFckrcLiLCSnpe>
(private link — the owner must share it before others can open it)

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

## How it works

```
question
   │
   ├─ 1. guards        PII  →  advice  →  performance          (ppfaq/guards.py)
   │                   any hit stops here with a polite refusal + an educational link
   │
   ├─ 2. scheme detect  "liquid fund" → PPLF                   (ppfaq/retriever.py)
   │                   hard-filters candidates so schemes can't be confused
   │
   ├─ 3. retrieve      TF-IDF cosine over 55 fact chunks
   │                   below 0.24 → "not in my sources"
   │                   no scheme named but the fact differs by scheme → ask which
   │
   └─ 4. answer        the chunk's pre-written ≤3-sentence fact
                       + "Last updated from sources: …"
                       + exactly one citation link
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
| PII | "My PAN is ABCDE1234F…" | PPFAS scheme list |
| Opinion / portfolio | "Should I buy this?", "Which is better?" | AMFI — Risks in mutual funds |
| Performance | "5-year returns?", "Did it beat the benchmark?" | PPFAS factsheet archive |

Every refusal still carries a link, because the UI contract is one citation on *every* answer.

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
  guards.py                 PII / advice / performance refusals
  retriever.py              tokeniser, TF-IDF, scheme detection
  assistant.py              orchestration, thresholds, answer shape
  cli.py                    terminal interface
corpus/
  corpus.json               55 fact chunks, each with its source
  schemes.json              AMC + scheme scope and aliases
  sources.csv               the 24 URLs, with what each was used for
web/
  index.html                UI for the local server
  standalone.template.html  hosted single-page build (JS port of the same logic)
dist/index.html             built hosted page (generated)
docs/
  sample-qa.md              12 worked queries (generated)
  disclaimer.md             the disclaimer snippet used in the UI
scripts/                    sample generator, standalone build, parity check
tests/                      21 tests
```

---

## Known limits

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
  same corpus files. `scripts/check_parity.*` guards the pair across 40 questions, but a change
  to one still has to be mirrored in the other.
- **Coverage is narrow on purpose.** Five schemes, one AMC. Taxation, NAV history, portfolio
  holdings and anything requiring a login are out of scope.
