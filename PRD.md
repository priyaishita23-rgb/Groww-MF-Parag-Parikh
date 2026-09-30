# PRD — MF Facts Desk

A facts-only mutual fund FAQ assistant for Groww, scoped to PPFAS schemes.

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 29 September 2026 |
| **Owner** | Ishita Priya |
| **Requirements source** | `Problemstatement.txt` — Mutual Fund FAQs (Facts-Only Q&A Assistant) |
| **Status** | v1 shipped and default; v2 pipeline built (39/44 parity); generation built, off by default |
| **Purpose** | Milestone deliverable #6 — product requirements + class demo spec |

Scheme scope confirmed as PPFAS Mutual Fund on 29 September 2026.

---

## 1. Problem

Retail investors comparing mutual fund schemes ask the same narrow set of factual
questions over and over — expense ratio, exit load, minimum SIP, ELSS lock-in,
riskometer, benchmark, how to pull a capital-gains statement. The answers are all
published, but they are scattered across scheme pages, monthly factsheets, TER
disclosures and KIM/SID documents. Finding them takes several clicks and some
knowledge of which document holds which fact.

Meanwhile, general-purpose chatbots answer these questions fluently and sometimes
wrongly, with no citation and no line between a published fact and an opinion about
whether you should invest.

**MF Facts Desk answers only the factual questions, only from public documents, and
puts the source link on every single answer — including on its refusals.**

## 2. Goals

| ID | Goal | Measure |
|---|---|---|
| G1 | Answer the common factual MF questions correctly | All 8 named question types in §5.1 answered from corpus |
| G2 | Make every answer traceable | 100% of answers carry exactly one citation URL |
| G3 | Never give investment advice | Advice-intent questions refused before retrieval runs |
| G4 | Never accept personal data | PII patterns refused, nothing logged or stored |
| G5 | Make staleness visible | Every fact answer carries a "last updated from sources" date |
| G6 | Be demoable in class | Runs with no install, no API key, no network |

### Non-goals

- Ranking, recommending or comparing schemes on quality.
- Computing, quoting or comparing returns, CAGR or XIRR.
- Portfolio review, goal planning or tax-saving strategy.
- Anything requiring a login, a transaction, or user-specific data.
- Coverage beyond the five schemes in §4.

## 3. Users

| User | Need | Success looks like |
|---|---|---|
| **Retail investor on Groww** comparing schemes | The exit load on one specific fund, right now, without reading a 60-page SID | Gets the figure and the document it came from in one turn |
| **Support / content team** answering repeat questions | A citable, consistent answer they can paste to a customer | Same answer every time, with the link already attached |
| **Course evaluator** | Evidence that scope, sourcing and guardrails were handled deliberately | Refusals demonstrate as clearly as answers do |

## 4. Scope

**AMC:** PPFAS Mutual Fund (PPFAS Asset Management Pvt. Ltd.)
**Distribution context:** Groww. Facts are sourced from AMC / SEBI / AMFI public pages, never from the Groww app back-end.
**Plans:** Direct — Growth.

| Code | Scheme | Category |
|---|---|---|
| PPFCF | Parag Parikh Flexi Cap Fund | Flexi cap equity |
| PPTSF | Parag Parikh ELSS Tax Saver Fund | ELSS (tax saver) |
| PPCHF | Parag Parikh Conservative Hybrid Fund | Conservative hybrid |
| PPDAAF | Parag Parikh Dynamic Asset Allocation Fund | Dynamic asset allocation |
| PPLF | Parag Parikh Liquid Fund | Liquid |

**Corpus:** 55 fact chunks drawn from **24 public pages** — PPFAS scheme pages, the
August 2026 monthly factsheet, TER statutory disclosures, KIM / SID / SAI documents,
Investor Desk statement pages, plus AMFI and SEBI reference pages. Registered in
[`corpus/sources.csv`](corpus/sources.csv) with the facts each source was used for.

Figures are quoted as at the **August 2026 factsheet (as on 31 August 2026)**; the
corpus was assembled on **29 September 2026**.

**Source rules.** Public sources only. No third-party blogs. No screenshots of app
back-end screens. Every chunk's `source_id` must resolve to a registered row in
`sources.csv`, and the chunk's URL must match that row.

## 5. Functional requirements

### 5.1 Answering

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Answer **expense ratio** per scheme | Must |
| FR-2 | Answer **exit load** per scheme, preserving graded and conditional structures intact (e.g. PPLF's day-1-to-6 ladder; the "above 10% of units" carve-out) | Must |
| FR-3 | Answer **ELSS lock-in** (3 years) | Must |
| FR-4 | Answer **minimum investment** and **minimum SIP** per scheme | Must |
| FR-5 | Answer **riskometer** per scheme, plus what the riskometer means | Must |
| FR-6 | Answer **benchmark** per scheme | Must |
| FR-7 | Answer **how to download a capital-gains statement** and an account statement | Must |
| FR-8 | Answer scheme **category**, **inception date**, **fund managers**, **plans**, **entry load** | Should |
| FR-9 | Point **NAV** and **AUM** questions at the official factsheet rather than quoting a figure that goes stale daily | Must |
| FR-10 | Cap every answer at **3 sentences** | Must |
| FR-11 | Attach **exactly one** citation link to every answer, refusals included | Must |
| FR-12 | Attach `Last updated from sources: <date>` to every fact answer | Must |

### 5.2 Retrieval behaviour

| ID | Requirement |
|---|---|
| FR-13 | Detect which scheme a question names, via an alias table (`"flexi cap"`, `"ppfcf"`, `"tax saver"`, `"80c"`, `"balanced advantage"` → `PPDAAF`, …), and hard-filter candidates to that scheme |
| FR-14 | Where a question names **no** scheme but the fact **differs by scheme**, ask which scheme is meant rather than guessing. Returning a confident figure for the wrong fund is the worst available failure |
| FR-15 | Where a question names **several** schemes, answer for the first and offer the others as a follow-up |
| FR-16 | Where the best match scores below the relevance floor, return "I don't have that in my sources" plus a statement of what *is* covered |
| FR-17 | Treat an out-of-vocabulary query term as the **rarest** term rather than a free one, so off-topic questions fall below the floor instead of latching onto one incidental keyword |

> FR-17 exists because of a real failure: under standard TF-IDF, *"What is the capital
> of France?"* collapses to `capital` — `france` carries zero weight — and matches the
> capital-gains chunk with false confidence. Giving unseen terms maximum IDF puts real
> mass on `france` and pushes the score below threshold.

### 5.3 Guardrails

Evaluated **in order, before retrieval**. Any hit stops the turn with a polite refusal
and an educational link.

| ID | Layer | Triggers | Link returned |
|---|---|---|---|
| GR-1 | **PII** | PAN `[A-Z]{5}[0-9]{4}[A-Z]`, Aadhaar, phone `[6-9]\d{9}`, email, folio / account numbers, 11–18 digit numbers, OTP, and the words *PAN card / Aadhaar / OTP / CVV / netbanking password* | PPFAS scheme list |
| GR-2 | **Advice / opinion** | "should I", "worth buying", "which is better", "best fund", "do you recommend", "my portfolio", "suitable for me", "will it grow", "predict", "forecast" | AMFI — Risks in mutual funds |
| GR-3 | **Performance** | "returns", "CAGR", "XIRR", "performance", "beat the benchmark", "outperformed", "NAV history", "track record", "alpha" | PPFAS factsheet archive |

**GR-4** — the PII refusal must state that nothing was stored.

**GR-5** — a plain factual *"what is the benchmark of X?"* carries no performance term
and must fall through to retrieval. Only phrasings asking the assistant to *judge or
compute* performance are stopped. Over-blocking FR-6 is a defect.

**GR-6** — guardrails are deterministic pattern matches, not model judgements, so they
cannot be talked around by how a question is phrased.

### 5.4 Privacy

| ID | Requirement |
|---|---|
| FR-18 | Questions are answered and discarded. No logging, no persistence, no session state |
| FR-19 | The hosted single-page build runs entirely in the browser and makes no network calls |

## 6. UI specification

Required elements, per the brief:

1. **Welcome line** — "Hi — I answer factual questions about five Parag Parikh (PPFAS) mutual fund schemes, and every answer comes with its official source link."
2. **Three example questions**, clickable:
   - What is the expense ratio of Parag Parikh Flexi Cap Fund?
   - What is the lock-in for the ELSS Tax Saver Fund?
   - What is the exit load on Parag Parikh Liquid Fund?
3. **Disclaimer**, in an amber notice block under the title, above the examples, visible before any answer can be read:

   > **Facts-only.** No investment advice. Figures are quoted from public AMC/SEBI/AMFI documents and can change — always confirm on the linked source.

4. **Footer** stating the corpus boundary — "Covers ⟨5 scheme names⟩. 55 facts drawn from 24 public AMC/SEBI/AMFI pages."

**Answer block:** answer text → optional follow-up line → `Last updated from sources: ⟨date⟩` → `Source: ⟨title⟩` as a link.

The disclaimer string is defined once in `ppfaq/assistant.py` and served to the local
UI, the hosted page, the CLI and the generated sample file, so the four cannot drift.

## 7. Technical architecture

```
question
   │
   ├─ 1. guards         PII → advice → performance          ppfaq/guards.py
   │                    any hit stops here, with a link
   │
   ├─ 2. scheme detect  "liquid fund" → PPLF                ppfaq/retriever.py
   │                    hard-filters so schemes can't be confused
   │
   ├─ 3. retrieve       cosine similarity over 55 fact chunks
   │                    below floor → "not in my sources"
   │                    scheme-varying fact, no scheme named → ask which
   │
   └─ 4. answer         the chunk's pre-written ≤3-sentence fact
                        + "Last updated from sources: …"
                        + exactly one citation link
```

**Answers are stored, not generated.** Each chunk holds the finished sentence *and*
the URL it came from, so an answer cannot drift from its citation, and no generation
step can invent a figure. Retrieval decides *which* fact to show; it never paraphrases
one. This is the central safety property of the design — for a facts-only product with
a hard citation contract, it is worth more than fluency.

### 7.1 v1 — shipped

| Component | Choice | Rationale |
|---|---|---|
| Chunking | Hand-assembled fact chunks, one per (scheme × topic), 55 total | Every number traceable to a document; no tearing of graded exit-load ladders |
| Retrieval | TF-IDF cosine, max-IDF for unseen terms (FR-17), relevance floor 0.24 | No dependencies; fully inspectable for a class demo |
| Generation | None — stored answers | Citation cannot drift from answer |
| Runtime | Python 3.9+ stdlib only, `python app.py` | Zero install, no API key, works offline |
| Hosted build | Single-page JS port over the same corpus files | Shareable link; no backend needed |

### 7.2 v2 — built, not yet at parity

**Status as of 30 September 2026.** The pipeline exists and runs. It is not the
default, because it answers 5 of 44 parity questions worse than v1.

| Requirement | Status |
|---|---|
| TR-1 chunking | **built** — recursive section-aware, numeric conditions protected, `chunks/chunks.txt` |
| TR-2 embeddings | **built** — all-MiniLM-L6-v2, 384-dim, local, `chunks/embeddings.txt` |
| TR-3 vector DB | **built** — ChromaDB persisted to `vectorstore/`, ingestion runs once |
| TR-4 retrieval | **built** — scheme pre-filter as a Chroma `where` clause, then vector search |
| TR-5 guards unchanged | **held** — deterministic, still ahead of retrieval, identical on both backends |
| TR-6 parity | **not met** — 39/44 |
| `MIN_SCORE_VECTOR` | **not set** — see below |

**The threshold was deliberately not chosen.** Calibration found no floor that
answers every in-scope question and refuses every out-of-scope one, on either
backend or either scoring quantity (`docs/calibration.txt`):

| backend · quantity | lowest in-scope | highest out-of-scope | overlap |
|---|---|---|---|
| tfidf · biased | 0.3364 | 0.3862 | 0.0497 |
| tfidf · raw | 0.2083 | 0.2357 | 0.0274 |
| vector · biased | 0.4239 | 0.8033 | 0.3794 |
| vector · raw | 0.4239 | 0.5533 | 0.1294 |

Picking a value anyway would have hidden this rather than fixed it. FR-16 is
therefore **partially met**: out-of-scope questions are refused by the guards and by
the floor, but 2 of 27 on `tfidf` and 6 of 27 on `vector` still return a nearest
fact. What remains are questions naming a covered fund while asking about a topic
the corpus does not hold — ISIN, modified duration, custodian, portfolio turnover.

**One finding changed the guard design.** The worst leaks were not a threshold
problem at all. *"lock-in for the ICICI ELSS fund"* scored 0.853 — above most
legitimate questions — because "elss" matches a scheme alias and the scheme bias
lifts it. An out-of-AMC guard now settles scope before retrieval, which closed that
category and cut the tfidf raw overlap from 0.2955 to 0.0274.

**The requirements this was built against:**

| ID | Requirement |
|---|---|
| TR-1 | **Chunking** — recursive section-aware chunking that preserves numeric conditions and does not tear tables or rule structures. Chunks written to a readable `.txt` for inspection before embedding |
| TR-2 | **Embeddings** — `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, run locally, no API key. Same model embeds chunks and queries |
| TR-3 | **Vector DB** — ChromaDB, persisted to disk, so ingestion runs once and not on every restart |
| TR-4 | **Retrieval** — scheme metadata pre-filter (FR-13) applied as a Chroma `where` clause, then vector search, then relevance floor |
| TR-5 | Guardrails (GR-1…GR-6) stay deterministic and stay **ahead** of retrieval, unchanged |
| TR-6 | Citation contract (FR-11) preserved: a cited URL must exist in the retrieved chunks |

**Acceptance for v2:** the parity script must show v2 answering the parity set
identically to v1 on all facts, with no new advice or performance leakage.
Currently 39/44 — `scripts/check_parity_v2.py`.

### 7.3 Generation — built, optional, off by default

`Problemstatement.txt` asks for a Retrieval **and Generation** stage. With
`GENERATION=on` the assistant phrases an answer with Gemini instead of returning the
stored sentence. It is off by default, so the demo path, the golden baseline and both
parity gates are unaffected.

| ID | Requirement |
|---|---|
| TR-7 | The model receives **only** the retrieved chunk. No outside knowledge, ≤3 sentences, no advice, no performance |
| TR-8 | The model **never supplies the citation**. Title, URL and as-of date are attached afterwards from the chunk retrieval selected, so a generated answer cannot cite a document it was not built from |
| TR-9 | Every numeric token in the generated text must already appear in the source chunk. Any failure discards the generation and uses the stored sentence |
| TR-10 | Fails closed: no key, network error, timeout, truncation or failed check all fall back silently |

TR-8 is the structural half of FR-11. The model is not trusted to cite correctly; it
is never given the opportunity.

**Two defects found in testing, both recorded because they generalise.**
`gemini-3.8-flash` is a thinking model and `maxOutputTokens` covers its reasoning as
well as the reply — at 256 it spent 242 tokens thinking, left 10 for the answer, and
returned a truncated fragment. The budget is now 1024, and this needs rechecking on
any model change. More importantly, the verifier *accepted* that fragment: truncated
output is fluent, short, and contains no numbers to check, so every content rule
passed while the answer said nothing. Verification now rejects any `finishReason`
other than `STOP`, and any text not ending in terminal punctuation.

**Generation is local-only.** `dist/index.html` runs in the browser and cannot hold
an API key, so the hosted page always returns stored answers.

## 8. Acceptance criteria

Enforced by 61 automated tests (`python -m unittest discover -s tests -v`), plus two
gates run explicitly: `tests/negatives.py` (out-of-scope and refusals on both
backends) and `tests/backends.py` (A11–A17 on both backends). Those two are named so
discovery skips them — the discovered suite reports the default backend's health and
stays green, while the gates report the vector backend's true state, which is
currently failing.

| # | Criterion | Test |
|---|---|---|
| A1 | Expense ratio answered per scheme | `test_expense_ratio_flexi_cap` |
| A2 | **ELSS expense ratio not confused with Flexi Cap** | `test_expense_ratio_elss_not_confused_with_flexi` |
| A3 | ELSS lock-in = 3 years | `test_elss_lock_in` |
| A4 | Graded exit load returned intact | `test_exit_load_liquid_fund` |
| A5 | Minimum SIP answered | `test_minimum_sip` |
| A6 | Riskometer answered | `test_riskometer` |
| A7 | Benchmark treated as fact, not performance | `test_benchmark_is_a_fact_not_a_performance_question` |
| A8 | Capital-gains statement answered | `test_capital_gains_statement` |
| A9 | Every answer carries exactly one citation | `test_every_answer_has_one_citation` |
| A10 | Every answer ≤ 3 sentences | `test_answers_are_at_most_three_sentences` |
| A11 | Buy/sell advice refused | `test_refuses_buy_sell_advice` |
| A12 | Performance questions refused | `test_refuses_performance` |
| A13 | PII refused | `test_refuses_pii` |
| A14 | PII refusal states nothing was stored | `test_pii_refusal_mentions_nothing_stored` |
| A15 | Off-topic question falls to fallback | `test_out_of_scope` |
| A16 | Ambiguous scheme → asks which, never guesses | `test_asks_which_scheme_instead_of_guessing` |
| A17 | NAV / AUM pointed at factsheet, not quoted | `test_nav_and_aum_are_pointed_at_the_factsheet_not_quoted` |
| A18 | Every chunk's source is registered | `test_every_chunk_source_is_registered` |
| A19 | Chunk URL matches registered source URL | `test_chunk_url_matches_registered_source_url` |
| A20 | Source count within brief | `test_source_count_within_brief` |
| A21 | Chunk IDs unique | `test_chunk_ids_unique` |

Plus `scripts/check_parity.py` + `check_parity.mjs` — the hosted JS page and the Python
service must answer 44 questions identically.

## 9. Class demo spec

**Format:** live, ~3 minutes. Runs offline — no API key, no install, no network.

**Setup:** `python app.py` → <http://127.0.0.1:8000>. Fallback: open `dist/index.html`
directly, which needs nothing at all.

### Run sheet

| # | Say | Type | Point out |
|---|---|---|---|
| 1 | "Facts-only assistant over five PPFAS schemes, 55 facts from 24 public pages." | — | Disclaimer + welcome line, before any question |
| 2 | "A straightforward fact." | *What is the expense ratio of Parag Parikh Flexi Cap Fund?* | The citation link and the as-of date |
| 3 | "Same question, different fund — this is where these systems usually fail." | *What is the expense ratio of the ELSS Tax Saver Fund?* | Different figure, correct scheme. Scheme detection hard-filters before retrieval |
| 4 | "A fact with structure that must not be torn apart." | *What is the exit load on Parag Parikh Liquid Fund?* | The full day-1-to-6 ladder, intact |
| 5 | "Now the refusals — this is the actual product." | *Should I buy Parag Parikh Flexi Cap?* | Facts-only refusal **with an educational link**. Never reached retrieval |
| 6 | "It won't compute returns either." | *What were the 5-year returns?* | Pointed at the official factsheet |
| 7 | "And it won't take personal data." | *My PAN is ABCDE1234F, what's my lock-in?* | Refusal states nothing was stored |
| 8 | "It asks rather than guesses." | *What is the minimum SIP?* | Asks which scheme — the fact differs by scheme |
| 9 | "And it knows what it doesn't know." | *What is the capital of France?* | Falls to "not in my sources" — the FR-17 max-IDF fix |

### Questions to expect

**"Where is ChromaDB / the embedding model?"** — v1 uses TF-IDF with stored answers so
the demo runs with zero dependencies and a citation can never drift from its answer.
The MiniLM + ChromaDB pipeline is specified in §7.2 with acceptance criteria, as v2.

**"Why not have an LLM write the answers?"** — the hard requirement is one correct
citation on every answer. Storing the finished sentence next to its URL makes drift
structurally impossible. Generation would buy fluency and risk the product's only
safety property.

**"What happens when the figures change?"** — they go stale; that is why every answer
carries an as-of date. Refresh from the linked sources and bump `corpus_last_updated`.

## 10. Deliverables

| # | Deliverable | Location | Status |
|---|---|---|---|
| 1 | Working prototype for class demo | `app.py` + `dist/index.html` | Done |
| 2 | Source list | `corpus/sources.csv` — 24 URLs | Done |
| 3 | README — setup, scope, known limits | `README.md` | Done |
| 4 | Sample Q&A, 5–10 queries with answers + links | `docs/sample-qa.md` — 12 queries | Done |
| 5 | Disclaimer snippet | `docs/disclaimer.md` | Done |
| 6 | PRD — requirements + class demo spec | `PRD.md` | This document |

Verified present on 30 September 2026. The demo run sheet in §9 was rehearsed
end to end against the running assistant on the same date: all eight question
steps behave as the sheet claims, so no corrections were needed.

**Beyond the brief**, also produced: `ARCHITECTURE.md`, `IMPLEMENTATION.md`,
`docs/calibration.txt` (the threshold sweep), and the three pipeline artefacts
`chunks/documents.txt`, `chunks/chunks.txt` and `chunks/embeddings.txt` — the
inspectable output of RAG stages 1, 2 and 3.

## 11. Known limits

- **Figures go stale.** TER changes through the month; riskometers are re-rated
  monthly. The corpus is a snapshot of the August 2026 factsheet. There is no scraper —
  the corpus was assembled by hand precisely so every number could be traced to a
  document.
- **No paraphrasing.** A question phrased far from corpus vocabulary falls through to
  the fallback rather than being answered loosely. That is the intended failure mode,
  but it costs recall.
- **Retrieval is lexical.** TF-IDF has no synonym knowledge beyond a small hand-built
  map; "charges", "TER" and "expense ratio" are mapped, a genuinely novel phrasing is
  not. §7.2 addresses this.
- **One citation per answer, by design.** Where a fact appears in both the factsheet
  and the KIM, only the source actually used is cited.
- **Two implementations.** The hosted page is a JS port of the Python logic over the
  same corpus. `scripts/check_parity.*` guards the pair across 44 questions, but a
  change to one must still be mirrored in the other.
- **Coverage is narrow on purpose.** Five schemes, one AMC. Taxation, NAV history,
  portfolio holdings and anything requiring a login are out of scope.
- **Not investment advice.** The product refuses advice by design; this is a course
  milestone, not a regulated advisory service.
