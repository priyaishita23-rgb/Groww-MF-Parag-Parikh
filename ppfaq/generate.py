"""RAG stage 6 — Generate. Optional, grounded, and checked before it is used.

Off by default. With `GENERATION=on` the assistant may phrase an answer with
an LLM instead of returning the corpus sentence verbatim. Two design choices
keep that from costing the citation contract (PRD FR-11).

**The model never supplies the citation.** It writes prose and nothing else.
The source title, URL and as-of date are attached afterwards by the caller,
taken from the chunk retrieval actually selected. A generated answer therefore
cannot cite a document it was not built from - not because the model is
trusted to behave, but because it is never given the opportunity.

**Every figure is checked against the source chunk.** The remaining risk is a
fluent sentence containing a number the chunk does not contain: an expense
ratio off by a decimal place, a lock-in of 5 years instead of 3. So each
numeric token in the generated text must appear in the chunk it came from. If
one does not, the generation is discarded and the stored sentence is used.
The fallback is silent to the user and recorded on the Answer for inspection.

Fails closed everywhere: no key, network error, timeout, empty response,
failed check - all return None, and the caller keeps the stored answer.

Uses urllib from the standard library rather than an SDK, so enabling this
adds no dependency and cannot break the zero-install path (rule R5).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from . import config

ENDPOINT = ("https://generativelanguage.googleapis.com/v1beta/models/"
            "{model}:generateContent?key={key}")

TIMEOUT_SECONDS = 20

SYSTEM = """\
You rephrase published mutual fund facts for a facts-only assistant.

Rules, all mandatory:
- Use ONLY the source text provided below. You have no other knowledge.
- Never introduce a number, percentage, date or name that is not in the source.
- Do not give advice, opinions, recommendations or comparisons.
- Do not discuss returns, performance or whether something is a good investment.
- At most 3 sentences. Plain, factual, no preamble, no bullet points.
- Do not add a URL, a source line or a date; those are attached separately.
- If the source does not answer the question, reply exactly: INSUFFICIENT

Question: {question}

Source text:
{source}

Answer:"""

#: Numbers worth checking: percentages, money, plain figures, years.
_NUMERIC = re.compile(r"\d[\d,]*(?:\.\d+)?")

#: Words that would mean the model started advising despite the prompt.
_LEAKED_ADVICE = re.compile(
    r"\b(should|recommend|advise|suitable|best choice|we suggest|you ought)\b", re.I)


@dataclass(frozen=True)
class Generated:
    text: str
    model: str


def available() -> bool:
    """True when generation is switched on and a key is present."""
    return bool(config.GENERATION and config.GEMINI_API_KEY
                and config.LLM_PROVIDER == "gemini")


def _sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if s.strip()]


def _numbers(text: str) -> List[str]:
    """Numeric tokens, normalised so 1,000 and 1000 compare equal."""
    return [m.group(0).replace(",", "").rstrip(".") for m in _NUMERIC.finditer(text)]


def verify(text: str, source: str, finish_reason: str = "STOP") -> Optional[str]:
    """None if the generated text is safe to use, else the reason it is not."""
    if not text or not text.strip():
        return "empty"
    # A truncated answer is the quiet failure here. Cut a sentence short and
    # what is left can still be fluent, numberless and under three sentences -
    # every content check passes while the answer says nothing. The model's own
    # finish reason is the reliable signal, and the terminal punctuation check
    # catches a stop the API did not flag.
    if finish_reason != "STOP":
        return "truncated (finishReason %s)" % finish_reason
    if not text.strip().endswith((".", "!", "?")):
        return "ends mid-sentence"
    if text.strip().upper().startswith("INSUFFICIENT"):
        return "model reported the source does not answer it"
    if len(_sentences(text)) > 3:
        return "more than 3 sentences (FR-10)"
    if _LEAKED_ADVICE.search(text):
        return "advisory language despite the prompt (GR-2)"
    if "http" in text.lower():
        return "model supplied a URL; citations are attached by us, not by it"

    allowed = set(_numbers(source))
    for number in _numbers(text):
        if number not in allowed:
            # The dangerous case: a plausible figure the source never stated.
            return "figure %r is not in the source chunk" % number
    return None


def _call(prompt: str):
    """Return (text, finish_reason), or (None, reason) on failure."""
    url = ENDPOINT.format(model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": config.TEMPERATURE,
            "maxOutputTokens": config.MAX_OUTPUT_TOKENS,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None, "request failed"  # fail closed; caller keeps the stored answer

    try:
        candidate = body["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text, candidate.get("finishReason", "UNKNOWN")
    except (KeyError, IndexError, TypeError):
        return None, "unexpected response shape"


def generate(question: str, source: str) -> Optional[Generated]:
    """Rephrase `source` to answer `question`, or None if it cannot be trusted.

    `source` is the retrieved chunk's own text. Nothing else reaches the model.
    """
    if not available() or not source:
        return None

    text, finish_reason = _call(
        SYSTEM.format(question=question.strip(), source=source.strip()))
    if text is None:
        return None

    text = text.strip().strip('"')
    if verify(text, source, finish_reason) is not None:
        return None
    return Generated(text=text, model=config.GEMINI_MODEL)
