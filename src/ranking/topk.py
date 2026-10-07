"""Deterministic Top-M selection for PYMK topology scores."""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedCandidate:
    """One scored candidate in its final deterministic rank order."""

    candidate_id: Hashable
    score: float


def select_top_m(scores: Mapping[Hashable, float], top_m: int) -> tuple[RankedCandidate, ...]:
    """Select finite scores by score descending, then candidate ID ascending.

    Serving graph IDs are canonical contiguous integer IDs, so their natural
    ordering is the stable candidate-ID tie-break contract.
    """

    if top_m < 0:
        raise ValueError("top_m must be non-negative")
    for score in scores.values():
        if not math.isfinite(score):
            raise ValueError("topology scores must be finite")
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return tuple(RankedCandidate(candidate_id, score) for candidate_id, score in ordered[:top_m])
