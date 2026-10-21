"""Deterministic bounded two-hop candidate retrieval."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from src.serving.graph_index import ServingGraphIndex


@dataclass(frozen=True)
class RetrievalConfig:
    """Limits for local two-hop expansion.

    ``first_hop_cap`` is applied to the sorted first-hop adjacency list before
    expansion. ``second_hop_cap`` is applied independently to each selected
    first-hop neighbor's sorted adjacency list. ``candidate_cap`` is applied
    after candidate collection, preserving deterministic discovery order.

    Candidate order is deterministic traversal order only; it is not a rank.
    """

    first_hop_cap: int | None = None
    second_hop_cap: int | None = None
    candidate_cap: int | None = None
    strategy: str = "deterministic"
    seed: int = 42

    def __post_init__(self) -> None:
        for name in ("first_hop_cap", "second_hop_cap", "candidate_cap"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative or None")
        if self.strategy != "deterministic":
            raise ValueError("only the 'deterministic' retrieval strategy is supported")


@dataclass(frozen=True)
class RetrievalStats:
    """Auditable expansion and truncation statistics for one query."""

    first_hop_seen: int
    first_hop_used: int
    second_hop_expansions: int
    candidates_before_cap: int
    candidates_returned: int
    truncated: bool
    first_hop_capped: bool = False
    second_hop_capped: bool = False
    candidate_capped: bool = False
    second_hop_seen: int = 0
    second_hop_used: int = 0
    excluded_self: int = 0
    excluded_existing_connection: int = 0
    duplicate_candidates: int = 0


@dataclass(frozen=True)
class RetrievalResult:
    """Candidate IDs and retrieval statistics for a bounded local query."""

    candidate_ids: tuple[Hashable, ...]
    stats: RetrievalStats


def _take_cap(
    values: tuple[Hashable, ...], cap: int | None
) -> tuple[tuple[Hashable, ...], bool]:
    if cap is None or len(values) <= cap:
        return values, False
    return values[:cap], True


def retrieve_bounded_two_hop_candidates(
    user_id: Hashable,
    graph: ServingGraphIndex,
    config: RetrievalConfig | None = None,
) -> RetrievalResult:
    """Retrieve bounded, duplicate-free two-hop candidates deterministically.

    Every candidate excludes the query user and its direct neighbors. A cap
    truncates only its documented stage. ``truncated`` is true when a first- or
    second-hop cap omits adjacency entries, or a candidate cap omits collected
    candidate IDs. With all caps set to ``None``, membership matches the exact
    unbounded two-hop reference implementation.
    """

    config = config or RetrievalConfig()
    first_hops = graph.neighbors(user_id)
    used_first_hops, first_hop_truncated = _take_cap(first_hops, config.first_hop_cap)
    direct_neighbors = frozenset(first_hops)

    candidates: list[Hashable] = []
    seen_candidates: set[Hashable] = set()
    second_hop_expansions = 0
    second_hop_seen = 0
    second_hop_used = 0
    excluded_self = 0
    excluded_existing_connection = 0
    duplicate_candidates = 0
    second_hop_truncated = False

    for middle in used_first_hops:
        all_middle_neighbors = graph.neighbors(middle)
        second_hop_seen += len(all_middle_neighbors)
        middle_neighbors, was_truncated = _take_cap(all_middle_neighbors, config.second_hop_cap)
        second_hop_used += len(middle_neighbors)
        second_hop_truncated = second_hop_truncated or was_truncated
        for candidate in middle_neighbors:
            second_hop_expansions += 1
            if candidate == user_id:
                excluded_self += 1
                continue
            if candidate in direct_neighbors:
                excluded_existing_connection += 1
                continue
            if candidate in seen_candidates:
                duplicate_candidates += 1
                continue
            seen_candidates.add(candidate)
            candidates.append(candidate)

    returned_candidates, candidate_truncated = _take_cap(
        tuple(candidates), config.candidate_cap
    )
    stats = RetrievalStats(
        first_hop_seen=len(first_hops),
        first_hop_used=len(used_first_hops),
        second_hop_expansions=second_hop_expansions,
        candidates_before_cap=len(candidates),
        candidates_returned=len(returned_candidates),
        truncated=first_hop_truncated or second_hop_truncated or candidate_truncated,
        first_hop_capped=first_hop_truncated,
        second_hop_capped=second_hop_truncated,
        candidate_capped=candidate_truncated,
        second_hop_seen=second_hop_seen,
        second_hop_used=second_hop_used,
        excluded_self=excluded_self,
        excluded_existing_connection=excluded_existing_connection,
        duplicate_candidates=duplicate_candidates,
    )
    return RetrievalResult(candidate_ids=returned_candidates, stats=stats)
