"""Facts-only mutual fund FAQ assistant over a small, citable corpus.

Scope: PPFAS Mutual Fund, five schemes. Sources: corpus/sources.csv.
"""

from .assistant import Assistant, Answer

__all__ = ["Assistant", "Answer"]
__version__ = "1.0.0"
