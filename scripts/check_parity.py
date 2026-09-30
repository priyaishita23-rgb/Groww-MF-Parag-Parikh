"""Write the Python assistant's answers for the parity question set.

    python scripts/check_parity.py && node scripts/check_parity.mjs
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ppfaq.assistant import Assistant  # noqa: E402

QUESTIONS = [
    "What is the expense ratio of Parag Parikh Flexi Cap Fund?",
    "ELSS tax saver expense ratio",
    "TER of PPFCF",
    "What is the lock-in for the ELSS fund?",
    "Exit load on Parag Parikh Liquid Fund?",
    "exit load flexi cap",
    "Minimum SIP amount for the flexi cap fund",
    "smallest SIP in the ELSS fund",
    "Riskometer of Parag Parikh Conservative Hybrid Fund",
    "how risky is the flexi cap fund",
    "What is the benchmark of the flexi cap fund?",
    "which index does PPCHF track",
    "How do I download my capital gains statement?",
    "how do I get my account statement",
    "where can I find the SID",
    "what schemes do you cover",
    "plans available in PPFAS funds",
    "when was the liquid fund launched",
    "who manages the flexi cap fund",
    "daily NAV of flexi cap",
    "tell me the AUM",
    "entry load?",
    "expense ratio",
    "what is the exit load",
    "min sip",
    "Should I buy Parag Parikh Flexi Cap Fund?",
    "Is the ELSS fund a good investment?",
    "Which is better, flexi cap or ELSS?",
    "How much should I invest in this?",
    "What were the 5 year returns of the flexi cap fund?",
    "Did it beat the benchmark?",
    "What is the CAGR of the liquid fund?",
    "My PAN is ABCDE1234F, what is my exit load?",
    "My aadhaar is 1234 5678 9012",
    "Call me on 9876543210",
    "email me at someone@example.com",
    "folio number 12345678",
    "What is the capital of France?",
    "who won the world cup",
    "compare expense ratio of flexi cap and elss",
    # Added with the Phase 6 guards. Without these the parity check passed
    # 40/40 while the hosted page was missing three guards the Python service
    # had gained - the set has to exercise a guard for parity to mean anything.
    "lock-in for the ICICI ELSS fund",
    "expense ratio of the HDFC Small Cap Fund",
    "my folio number is 12345678",
    "is the liquid fund safe for me",
]


def main() -> None:
    assistant = Assistant()
    rows = []
    for question in QUESTIONS:
        a = assistant.ask(question)
        rows.append({
            "question": question,
            "kind": a.kind,
            "chunk_id": a.chunk_id,
            "source_url": a.source_url,
            "score": a.score,
        })
    out = os.path.join(ROOT, "scratch", "python-answers.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print(f"wrote {out} ({len(rows)} questions)")


if __name__ == "__main__":
    main()
