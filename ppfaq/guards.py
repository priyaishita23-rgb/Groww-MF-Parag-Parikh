"""Input guards: decide *before* retrieval whether a question can be answered at all.

Three things get stopped here:

1. PII        - the assistant must never accept or store PAN, Aadhaar, folio /
                account numbers, OTPs, emails or phone numbers.
2. Advice     - opinionated or portfolio questions ("should I buy?") get a polite
                facts-only refusal plus an educational link.
3. Performance- returns / CAGR / "which performed better" are not computed or
                compared here; the user is pointed at the official factsheet.

Order matters: PII first (nothing else should look at the text), then advice,
then performance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# --- links used by refusals (all from corpus/sources.csv) -------------------
EDUCATION_LINK = (
    "AMFI - Risks in mutual funds",
    "https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds",
)
FACTSHEET_LINK = (
    "PPFAS - Factsheet archive",
    "https://amc.ppfas.com/downloads/factsheet/",
)
SCOPE_LINK = (
    "PPFAS - Schemes",
    "https://amc.ppfas.com/schemes/",
)

# --- PII patterns -----------------------------------------------------------
_PII_PATTERNS = [
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)),
    ("Aadhaar", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("phone number", re.compile(r"(?:\+91[ -]?)?\b[6-9]\d{9}\b")),
    ("email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("bank or folio number", re.compile(r"\b(?:folio|a/c|acc(?:ount)?)\s*(?:no\.?|number|#)?\s*[:\-]?\s*\w*\d{4,}\b", re.I)),
    ("long account number", re.compile(r"\b\d{11,18}\b")),
    ("OTP", re.compile(r"\botp\b\s*(?:is|:)?\s*\d{4,8}\b", re.I)),
]
_PII_WORDS = re.compile(r"\b(pan\s*card|aadhaar|aadhar|otp|cvv|net\s*banking\s*password)\b", re.I)
# "my folio number is 12345678" - the label and the digits separated by words.
_PII_LABELLED_NUMBER = re.compile(
    r"\b(folio|account|a/c|policy|client\s*id|customer\s*id)\b[^.?!]{0,24}?\b\d{6,}\b",
    re.I,
)

# --- advice / opinion patterns ---------------------------------------------
_ADVICE = re.compile(
    r"\b("
    r"should i|shall i|should we|can i trust|"
    r"(good|bad|safe|wise|smart|great|solid|reliable|poor)\s+"
    r"(investment|fund|scheme|option|choice|idea|buy|bet|pick)|"
    r"is it (a )?(good|bad|safe|wise|smart)|"
    r"worth (it|buying|investing)|do you recommend|recommend(ation)?s?\b|advice|advise|"
    r"which (one )?(is|would be) (better|best)|what.s better|better (fund|scheme|option)|"
    r"best (fund|scheme|mutual fund|option|choice)|"
    r"my portfolio|my (existing )?(investment|holdings)|rebalance|asset allocation for me|"
    r"how much should i (invest|put)|suitable for me|right for me|"
    # "is the liquid fund safe for me" - the adjective is separated from the
    # noun, so the (good|safe|...)\s+(fund|scheme|...) alternative misses it.
    r"(good|bad|safe|wise|smart|risky)\s+(for|to)\s+(me|invest|buy)|"
    r"buy or sell|switch out of|exit (now|this fund)|hold or (sell|redeem)|"
    r"will (it|this) (go up|grow|fall|crash|double)|predict|forecast|outlook|"
    r"tax saving strategy|save the most tax"
    r")\b",
    re.I,
)

# --- performance patterns ---------------------------------------------------
_PERFORMANCE = re.compile(
    r"\b("
    r"returns?|cagr|xirr|performance|performed|annualis?zed|"
    r"how much (did|has|would) (it|this|i) (give|gain|return|make|earn|grow)|"
    r"beat the (benchmark|index|market)|outperform(ed|ance)?|underperform(ed)?|"
    r"nav (history|trend|movement)|past (year|3 years|5 years) (return|performance)|"
    r"alpha\b|track record"
    r")\b",
    re.I,
)
# A plain "what is the benchmark of X?" carries no performance term, so it falls
# through to retrieval. Only these phrasings, which ask us to judge or compute
# performance, are stopped.


# --- other fund houses ------------------------------------------------------
# Calibration (scripts/calibrate.py) showed these are the leak no threshold can
# close. "lock-in for the ICICI ELSS fund" scores 0.853 on the vector backend -
# higher than most legitimate questions - because "elss" matches a scheme alias,
# the hard filter narrows to the PPFAS ELSS, and the +0.25 scheme bias lifts it.
# The question is semantically identical to one we should answer; the only
# difference is a fund house this corpus does not cover. That is a scope
# decision, not a similarity one, so it is settled deterministically and before
# retrieval, like every other guard here.
_OTHER_AMCS = re.compile(
    r"\b("
    r"hdfc|icici|sbi|axis|kotak|nippon|aditya\s*birla|absl|uti|dsp|mirae|"
    r"franklin|templeton|tata|canara|robeco|edelweiss|quant|motilal|oswal|"
    r"invesco|sundaram|bandhan|hsbc|lic\s*mf|baroda|bnp|pgim|navi|whiteoak|"
    r"white\s*oak|360\s*one|helios|bajaj|samco|iti|shriram|mahindra|"
    r"jm\s*financial|old\s*bridge|unifi|zerodha|nj\s*mutual|trust\s*mutual"
    r")\b",
    re.I,
)


def other_amc(question: str) -> Optional[str]:
    """The name of a fund house outside this corpus, if the question names one.

    Returns the matched text so the reply can say which one. Kept separate
    from `check` because the outcome is "not in my sources" rather than a
    refusal - the question is perfectly legitimate, just out of scope.
    """
    match = _OTHER_AMCS.search(question or "")
    return match.group(0) if match else None


@dataclass(frozen=True)
class Refusal:
    kind: str           # "pii" | "advice" | "performance"
    message: str
    link_title: str
    link_url: str


def _pii_kind(question: str) -> Optional[str]:
    if _PII_WORDS.search(question):
        return "personal identifiers"
    if _PII_LABELLED_NUMBER.search(question):
        return "bank or folio number"
    for label, pattern in _PII_PATTERNS:
        if pattern.search(question):
            return label
    return None


def check(question: str) -> Optional[Refusal]:
    """Return a Refusal if the question must not be answered, else None."""
    q = (question or "").strip()
    if not q:
        return None

    found = _pii_kind(q)
    if found:
        return Refusal(
            kind="pii",
            message=(
                f"I can't take a {found} here, and nothing you typed has been stored. "
                "Please re-ask without any personal or account details - I only answer "
                "general scheme facts from public documents."
            ),
            link_title=SCOPE_LINK[0],
            link_url=SCOPE_LINK[1],
        )

    if _ADVICE.search(q):
        return Refusal(
            kind="advice",
            message=(
                "I'm a facts-only assistant, so I can't say whether a scheme suits you or "
                "comment on your portfolio. I can quote published facts such as expense "
                "ratio, exit load, lock-in, minimum SIP, riskometer or benchmark."
            ),
            link_title=EDUCATION_LINK[0],
            link_url=EDUCATION_LINK[1],
        )

    if _PERFORMANCE.search(q):
        return Refusal(
            kind="performance",
            message=(
                "I don't calculate or compare returns. Scheme performance is published "
                "in the AMC's official monthly factsheet, which is the right place to "
                "read it alongside the standard disclaimers."
            ),
            link_title=FACTSHEET_LINK[0],
            link_url=FACTSHEET_LINK[1],
        )

    return None
