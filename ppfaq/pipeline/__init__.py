"""The v2 ingestion pipeline: Load → Chunk → Embed → Store.

Each stage is a separate module so it can be run, inspected and explained on its
own. Stage 1 lives here; chunking is `ppfaq.chunking`, embedding and storage
arrive in Phase 4.

Nothing in this package is reachable from `Assistant` on the default backend —
v1 keeps loading the corpus through `ppfaq.corpus` exactly as before.
"""

from __future__ import annotations

from .load import SourceDocument, describe_documents, load_documents

__all__ = ["SourceDocument", "load_documents", "describe_documents"]
