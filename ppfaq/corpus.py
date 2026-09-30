"""Loading of the fact corpus, the scheme list and the source register."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from typing import Dict, List

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus")


@dataclass(frozen=True)
class Chunk:
    id: str
    scheme: str
    topic: str
    keywords: str
    answer: str
    source_id: str
    source_title: str
    source_url: str
    as_on: str

    @property
    def text(self) -> str:
        return " ".join([self.topic.replace("_", " "), self.keywords, self.answer])


@dataclass(frozen=True)
class Scheme:
    code: str
    name: str
    aliases: List[str]


def _path(name: str) -> str:
    return os.path.join(CORPUS_DIR, name)


def load_chunks() -> List[Chunk]:
    with open(_path("corpus.json"), encoding="utf-8") as fh:
        return [Chunk(**row) for row in json.load(fh)]


def load_schemes() -> Dict[str, Scheme]:
    with open(_path("schemes.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    return {s["code"]: Scheme(s["code"], s["name"], s["aliases"]) for s in raw["schemes"]}


def load_meta() -> dict:
    with open(_path("schemes.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    raw.pop("schemes", None)
    return raw


def load_sources() -> Dict[str, dict]:
    with open(_path("sources.csv"), encoding="utf-8", newline="") as fh:
        return {row["id"]: row for row in csv.DictReader(fh)}
