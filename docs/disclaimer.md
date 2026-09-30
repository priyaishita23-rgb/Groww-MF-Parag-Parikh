# Disclaimer snippet

The exact string shown in the UI. It is defined once, in `ppfaq/assistant.py` as `DISCLAIMER`,
and is served to both the local UI (`/api/meta`) and the hosted page, so the two cannot differ.

---

> **Facts-only.** No investment advice. Figures are quoted from public AMC/SEBI/AMFI documents
> and can change — always confirm on the linked source.

---

## Where it appears

- **Local UI** — an amber notice block directly under the page title, above the example
  questions, before any answer can be read.
- **Hosted page** — the same notice, with "Facts-only." set as the label of the block.
- **CLI** — printed under the welcome line at startup.
- **`docs/sample-qa.md`** — quoted at the top of the generated file.

## Supporting lines in the UI

| Line | Where | Purpose |
|---|---|---|
| "Hi — I answer factual questions about five Parag Parikh (PPFAS) mutual fund schemes, and every answer comes with its official source link." | Welcome line | Sets scope before the first question |
| "Last updated from sources: \<date\>" | On every fact answer | Makes staleness visible |
| "Source: \<title\>" (link) | On every answer, refusals included | The one citation |
| "Covers \<5 scheme names\>. 55 facts drawn from 24 public AMC/SEBI/AMFI pages." | Footer | States the corpus boundary |

## Refusal wording

Opinion / portfolio questions:

> I'm a facts-only assistant, so I can't say whether a scheme suits you or comment on your
> portfolio. I can quote published facts such as expense ratio, exit load, lock-in, minimum SIP,
> riskometer or benchmark.

Performance questions:

> I don't calculate or compare returns. Scheme performance is published in the AMC's official
> monthly factsheet, which is the right place to read it alongside the standard disclaimers.

Personal or account details:

> I can't take a \<PAN / Aadhaar / phone number / …\> here, and nothing you typed has been
> stored. Please re-ask without any personal or account details — I only answer general scheme
> facts from public documents.
