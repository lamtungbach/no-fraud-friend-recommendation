"""Configuration for deterministic topology ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RankingMethod = Literal["cn", "aa", "jaccard", "pa"]


@dataclass(frozen=True)
class RankingConfig:
    """Select a topology score and the number of results to return."""

    ranking_method: RankingMethod = "cn"
    top_m: int = 10

    def __post_init__(self) -> None:
        if self.ranking_method not in {"cn", "aa", "jaccard", "pa"}:
            raise ValueError("ranking_method must be one of: cn, aa, jaccard, pa")
        if self.top_m < 0:
            raise ValueError("top_m must be non-negative")
