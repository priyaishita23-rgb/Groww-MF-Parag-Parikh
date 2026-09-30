"""Regenerate docs/sample-qa.md straight from the assistant, so the file can
never drift from what the prototype actually answers.

    python scripts/make_samples.py
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppfaq.assistant import DISCLAIMER, Assistant  # noqa: E402

QUESTIONS = [
    ("Fact - expense ratio", "What is the expense ratio of Parag Parikh Flexi Cap Fund?"),
    ("Fact - ELSS lock-in", "What is the lock-in period for the ELSS Tax Saver Fund?"),
    ("Fact - exit load", "What is the exit load on Parag Parikh Liquid Fund?"),
    ("Fact - minimum SIP", "What is the minimum SIP for the Conservative Hybrid Fund?"),
    ("Fact - riskometer", "What does the riskometer say for Parag Parikh Dynamic Asset Allocation Fund?"),
    ("Fact - benchmark", "Which benchmark does the ELSS Tax Saver Fund use?"),
    ("Fact - statements", "How do I download my capital gains statement?"),
    ("Ambiguous - asks which scheme", "What is the exit load?"),
    ("Refusal - opinion", "Should I buy Parag Parikh Flexi Cap Fund?"),
    ("Refusal - performance", "What were the 5-year returns of the flexi cap fund?"),
    ("Refusal - PII", "My PAN is ABCDE1234F, can you check my exit load?"),
    ("Out of scope", "What is the capital of France?"),
]


def main() -> None:
    assistant = Assistant()
    out = [
        "# Sample Q&A",
        "",
        f"Generated from the running assistant on {date.today().isoformat()} "
        "by `python scripts/make_samples.py`. Do not edit by hand.",
        "",
        f"> {DISCLAIMER}",
        "",
    ]
    for label, question in QUESTIONS:
        answer = assistant.ask(question)
        out.append(f"### {label}")
        out.append("")
        out.append(f"**Q. {question}**")
        out.append("")
        out.append(answer.text)
        if answer.followup:
            out.append("")
            out.append(f"_{answer.followup}_")
        out.append("")
        if answer.as_on:
            out.append(f"Last updated from sources: {answer.as_on}  ")
        out.append(f"Source: [{answer.source_title}]({answer.source_url})")
        out.append("")
        out.append(f"<sub>route: `{answer.kind}`"
                   + (f" · chunk `{answer.chunk_id}` · score `{answer.score}`" if answer.chunk_id else "")
                   + "</sub>")
        out.append("")

    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "sample-qa.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print(f"wrote {path} ({len(QUESTIONS)} questions)")


if __name__ == "__main__":
    main()
