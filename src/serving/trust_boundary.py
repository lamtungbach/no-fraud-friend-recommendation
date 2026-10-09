"""Trust/Fraud boundary for deriving uncached Safe Top-K from raw PYMK Top-M.

This module deliberately owns no graph or Trust-model logic. Providers convert a
Trust implementation into a small, implementation-neutral domain contract; the
merger then applies an explicit, fail-safe serving policy.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.serving.recommendation_engine import Recommendation, RecommendationResult
    from src.trust.service import TrustService


class Eligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    SUSPICIOUS = "SUSPICIOUS"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class TrustAction(str, Enum):
    KEEP = "KEEP"
    DROP = "DROP"
    DOWNRANK = "DOWNRANK"


@dataclass(frozen=True)
class TrustCandidateResult:
    candidate_id: Hashable
    eligibility: Eligibility
    risk_score: float | None = None
    trust_score: float | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class TrustBatchResult:
    candidates: tuple[TrustCandidateResult, ...]
    trust_version: str


@dataclass(frozen=True)
class TrustRerankCandidateInput:
    """Minimal input shape consumed by ``TrustService.rerank_candidates``.

    Keeping this DTO at the boundary avoids importing Trust's HTTP/Pydantic
    schema into raw recommendation serving while preserving the attributes the
    existing in-process service reads.
    """

    candidate_id: int
    pymk_score: float
    mutual_tier1_count: int


class TrustProviderError(RuntimeError):
    """The Trust provider could not produce a complete trustworthy response."""


class MutualTier1CountProvider(Protocol):
    """Supplies verified Tier-1 mutual counts for Trust Tier-3 admission.

    Missing keys mean that no authoritative count was available. They are never
    replaced with a fabricated zero by this boundary.
    """

    def batch_count(self, user_id: int, candidate_ids: Sequence[int]) -> Mapping[int, int]: ...


@runtime_checkable
class TrustEligibilityProvider(Protocol):
    """Implementation-neutral, synchronous Trust eligibility boundary.

    ``pymk_scores`` is optional so simple providers only need IDs. The in-process
    TrustService adapter receives it to construct its existing re-rank inputs.
    """

    def batch_check(
        self,
        user_id: Hashable,
        candidate_ids: Sequence[Hashable],
        *,
        pymk_scores: Mapping[Hashable, float] | None = None,
    ) -> TrustBatchResult: ...


@dataclass(frozen=True)
class TrustPolicy:
    """Serving policy. Defaults are fail-safe and require mentor confirmation."""

    blocked_action: TrustAction = TrustAction.DROP
    suspicious_action: TrustAction = TrustAction.DROP
    unknown_action: TrustAction = TrustAction.DROP
    provider_error_action: TrustAction = TrustAction.DROP
    missing_profile_action: TrustAction = TrustAction.DROP
    missing_result_action: TrustAction = TrustAction.DROP
    version: str = "phase06-fail-safe-v1"


@dataclass(frozen=True)
class SafeRecommendation:
    """A raw PYMK recommendation with the Trust decision used at serving time."""

    candidate_id: Hashable
    score: float
    rank: int
    eligibility: Eligibility
    risk_score: float | None
    trust_score: float | None
    reason_code: str | None


@dataclass(frozen=True)
class SafeRecommendationResult:
    user_id: Hashable
    recommendations: tuple[SafeRecommendation, ...]
    graph_version: str
    trust_version: str
    trust_policy_version: str
    raw_cache_hit: bool


class AllowAllTrustProvider:
    """Deterministic local provider for deployments without Trust integration."""

    def __init__(self, trust_version: str = "allow-all-v1"):
        self._trust_version = trust_version

    def batch_check(
        self,
        user_id: Hashable,
        candidate_ids: Sequence[Hashable],
        *,
        pymk_scores: Mapping[Hashable, float] | None = None,
    ) -> TrustBatchResult:
        del user_id, pymk_scores
        return TrustBatchResult(
            candidates=tuple(
                TrustCandidateResult(candidate_id=candidate_id, eligibility=Eligibility.ELIGIBLE)
                for candidate_id in candidate_ids
            ),
            trust_version=self._trust_version,
        )


class MockTrustProvider:
    """Programmable provider for tests and local integration without TrustService."""

    def __init__(
        self,
        result: TrustBatchResult | None = None,
        *,
        trust_version: str = "mock-v1",
        error: Exception | None = None,
    ):
        self.result = result
        self.trust_version = trust_version
        self.error = error
        self.calls: list[tuple[Hashable, tuple[Hashable, ...]]] = []

    def batch_check(
        self,
        user_id: Hashable,
        candidate_ids: Sequence[Hashable],
        *,
        pymk_scores: Mapping[Hashable, float] | None = None,
    ) -> TrustBatchResult:
        del pymk_scores
        self.calls.append((user_id, tuple(candidate_ids)))
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return TrustBatchResult(
            candidates=tuple(
                TrustCandidateResult(candidate_id=candidate_id, eligibility=Eligibility.ELIGIBLE)
                for candidate_id in candidate_ids
            ),
            trust_version=self.trust_version,
        )


class TrustServiceEligibilityProvider:
    """Adapter for Linh's existing ``TrustService`` without changing it.

    TrustService accepts integer IDs. Invalid generic graph IDs and unavailable
    Tier-3 mutual counts are returned as UNKNOWN decisions instead of coerced
    values. Missing profiles are also surfaced distinctly for policy handling.
    """

    def __init__(
        self,
        trust_service: TrustService,
        *,
        mutual_tier1_counts: MutualTier1CountProvider | None = None,
        trust_version: str = "trust-service-v1",
        tier3_threshold: int = 5,
    ):
        if not trust_version:
            raise ValueError("trust_version must be non-empty")
        if tier3_threshold < 1:
            raise ValueError("tier3_threshold must be positive")
        self._trust_service = trust_service
        self._mutual_tier1_counts = mutual_tier1_counts
        self._trust_version = trust_version
        self._tier3_threshold = tier3_threshold

    def batch_check(
        self,
        user_id: Hashable,
        candidate_ids: Sequence[Hashable],
        *,
        pymk_scores: Mapping[Hashable, float] | None = None,
    ) -> TrustBatchResult:
        if not _is_trust_id(user_id):
            return self._unknown_all(candidate_ids, "INVALID_TRUST_USER_ID")

        unique_ids = _unique(candidate_ids)
        results: dict[Hashable, TrustCandidateResult] = {}
        valid_ids: list[int] = []
        for candidate_id in unique_ids:
            if not _is_trust_id(candidate_id):
                results[candidate_id] = _unknown(candidate_id, "INVALID_TRUST_CANDIDATE_ID")
            else:
                valid_ids.append(candidate_id)

        # Inspecting profiles only decides whether to call the existing Trust
        # re-ranker; no tier, score, or admission rule is reimplemented here.
        tier3_ids: list[int] = []
        rerank_ids: list[int] = []
        for candidate_id in valid_ids:
            profile = self._trust_service.get_user_profile(candidate_id)
            if profile is None:
                results[candidate_id] = _unknown(candidate_id, "TRUST_PROFILE_MISSING")
                continue
            if profile.recommendation_tier.value == "TIER_3_RESTRICTED_CAUTION":
                tier3_ids.append(candidate_id)
            rerank_ids.append(candidate_id)

        mutual_counts: Mapping[int, int] = {}
        if tier3_ids:
            if self._mutual_tier1_counts is not None:
                mutual_counts = self._mutual_tier1_counts.batch_count(user_id, tier3_ids)
            for candidate_id in tier3_ids:
                count = mutual_counts.get(candidate_id)
                if not _is_valid_count(count):
                    results[candidate_id] = _unknown(
                        candidate_id, "MUTUAL_TIER1_COUNT_UNAVAILABLE"
                    )

        allowed_for_rerank = [candidate_id for candidate_id in rerank_ids if candidate_id not in results]
        if allowed_for_rerank:
            inputs = [
                TrustRerankCandidateInput(
                    candidate_id=candidate_id,
                    pymk_score=_safe_pymk_score(pymk_scores, candidate_id),
                    # The count is immaterial outside Tier 3. Tier-3 entries are
                    # present only after an authoritative count was supplied.
                    mutual_tier1_count=mutual_counts.get(candidate_id, 0),
                )
                for candidate_id in allowed_for_rerank
            ]
            reranked = self._trust_service.rerank_candidates(
                target_user_id=user_id,
                candidates=inputs,
                tier3_threshold=self._tier3_threshold,
            )
            items = tuple(reranked.ranked_candidates) + tuple(reranked.blocked_candidates)
            seen: set[int] = set()
            for item in items:
                if item.candidate_id not in allowed_for_rerank or item.candidate_id in seen:
                    continue
                seen.add(item.candidate_id)
                profile = self._trust_service.get_user_profile(item.candidate_id)
                eligibility = (
                    Eligibility.SUSPICIOUS
                    if item.is_allowed
                    and profile is not None
                    and profile.recommendation_tier.value == "TIER_3_RESTRICTED_CAUTION"
                    else Eligibility.ELIGIBLE
                    if item.is_allowed
                    else Eligibility.BLOCKED
                )
                results[item.candidate_id] = TrustCandidateResult(
                    candidate_id=item.candidate_id,
                    eligibility=eligibility,
                    risk_score=profile.p_bot if profile is not None else None,
                    trust_score=item.trust_score,
                    reason_code=item.reason,
                )
            for candidate_id in allowed_for_rerank:
                results.setdefault(candidate_id, _unknown(candidate_id, "TRUST_RESULT_MISSING"))

        return TrustBatchResult(
            candidates=tuple(results[candidate_id] for candidate_id in unique_ids),
            trust_version=self._trust_version,
        )

    def _unknown_all(
        self, candidate_ids: Sequence[Hashable], reason_code: str
    ) -> TrustBatchResult:
        return TrustBatchResult(
            candidates=tuple(_unknown(candidate_id, reason_code) for candidate_id in _unique(candidate_ids)),
            trust_version=self._trust_version,
        )


class SafeTopKMerger:
    """Applies Trust policy without caching Safe Top-K or changing raw ranks."""

    def __init__(self, policy: TrustPolicy | None = None):
        self._policy = policy or TrustPolicy()

    @property
    def policy(self) -> TrustPolicy:
        return self._policy

    def merge(
        self,
        raw_result: RecommendationResult,
        top_k: int,
        provider: TrustEligibilityProvider,
    ) -> SafeRecommendationResult:
        if top_k < 0:
            raise ValueError("top_k must be non-negative")
        raw = _dedupe_recommendations(raw_result.recommendations)
        scores = {item.candidate_id: item.score for item in raw}
        try:
            batch = provider.batch_check(
                raw_result.user_id,
                [item.candidate_id for item in raw],
                pymk_scores=scores,
            )
            decisions = _normalise_decisions(raw, batch)
            trust_version = batch.trust_version or "unknown"
            error_action: TrustAction | None = None
        except Exception:  # noqa: BLE001 - a provider is an external fault boundary.
            # Fail closed by default. Providers may use TimeoutError or their own
            # transport exception; neither becomes ELIGIBLE silently.
            decisions = {
                item.candidate_id: _unknown(item.candidate_id, "TRUST_PROVIDER_ERROR")
                for item in raw
            }
            trust_version = "unavailable"
            error_action = self._policy.provider_error_action

        keep: list[SafeRecommendation] = []
        downrank: list[SafeRecommendation] = []
        for item in raw:
            decision = decisions[item.candidate_id]
            action = error_action or self._action_for(decision)
            safe = SafeRecommendation(
                candidate_id=item.candidate_id,
                score=item.score,
                rank=item.rank,
                eligibility=decision.eligibility,
                risk_score=decision.risk_score,
                trust_score=decision.trust_score,
                reason_code=decision.reason_code,
            )
            if action is TrustAction.KEEP:
                keep.append(safe)
            elif action is TrustAction.DOWNRANK:
                downrank.append(safe)
        # Stable partitions preserve raw PYMK order within an action class; thus
        # the policy down-rank is deterministic without inventing a score formula.
        return SafeRecommendationResult(
            user_id=raw_result.user_id,
            recommendations=tuple((keep + downrank)[:top_k]),
            graph_version=raw_result.graph_version,
            trust_version=trust_version,
            trust_policy_version=self._policy.version,
            raw_cache_hit=raw_result.cache_hit,
        )

    def _action_for(self, decision: TrustCandidateResult) -> TrustAction:
        if decision.reason_code == "TRUST_PROFILE_MISSING":
            return self._policy.missing_profile_action
        if decision.reason_code == "TRUST_RESULT_MISSING":
            return self._policy.missing_result_action
        return {
            Eligibility.ELIGIBLE: TrustAction.KEEP,
            Eligibility.SUSPICIOUS: self._policy.suspicious_action,
            Eligibility.BLOCKED: self._policy.blocked_action,
            Eligibility.UNKNOWN: self._policy.unknown_action,
        }[decision.eligibility]


def _normalise_decisions(
    raw: Sequence[Recommendation], batch: TrustBatchResult
) -> dict[Hashable, TrustCandidateResult]:
    raw_ids = {item.candidate_id for item in raw}
    decisions: dict[Hashable, TrustCandidateResult] = {}
    for result in batch.candidates:
        if result.candidate_id not in raw_ids or result.candidate_id in decisions:
            continue
        if not _valid_optional_score(result.risk_score) or not _valid_optional_score(result.trust_score):
            decisions[result.candidate_id] = _unknown(result.candidate_id, "INVALID_TRUST_SCORE")
        else:
            decisions[result.candidate_id] = result
    for item in raw:
        decisions.setdefault(item.candidate_id, _unknown(item.candidate_id, "TRUST_RESULT_MISSING"))
    return decisions


def _dedupe_recommendations(items: Sequence[Recommendation]) -> tuple[Recommendation, ...]:
    seen: set[Hashable] = set()
    unique: list[Recommendation] = []
    for item in items:
        if item.candidate_id not in seen:
            seen.add(item.candidate_id)
            unique.append(item)
    return tuple(unique)


def _unique(items: Sequence[Hashable]) -> tuple[Hashable, ...]:
    seen: set[Hashable] = set()
    return tuple(item for item in items if not (item in seen or seen.add(item)))


def _unknown(candidate_id: Hashable, reason_code: str) -> TrustCandidateResult:
    return TrustCandidateResult(
        candidate_id=candidate_id,
        eligibility=Eligibility.UNKNOWN,
        reason_code=reason_code,
    )


def _is_trust_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _safe_pymk_score(scores: Mapping[Hashable, float] | None, candidate_id: Hashable) -> float:
    value = scores.get(candidate_id, 0.0) if scores is not None else 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) and score >= 0.0 else 0.0


def _valid_optional_score(value: float | None) -> bool:
    if value is None:
        return True
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
