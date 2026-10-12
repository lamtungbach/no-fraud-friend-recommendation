# Phase 06 Trust boundary policy

`RecommendationEngine.recommend()` remains the raw, cacheable PYMK Top-M API.
`RecommendationEngine.recommend_safe()` fetches that raw Top-M and derives an
uncached Safe Top-K at request time through `TrustEligibilityProvider`.

Default policy `phase06-fail-safe-v1` is intentionally conservative:

| Condition | Default action |
| --- | --- |
| `ELIGIBLE` | `KEEP` |
| `SUSPICIOUS` | `DROP` |
| `BLOCKED` | `DROP` |
| `UNKNOWN` | `DROP` |
| timeout/provider error | `DROP` |
| missing Trust profile | `DROP` |
| missing candidate result | `DROP` |

`DOWNRANK` is a stable partition: all retained `KEEP` candidates preserve raw
PYMK order, followed by retained down-ranked candidates in raw PYMK order. This
is deterministic and avoids inventing a new Trust score formula.

The `TrustServiceEligibilityProvider` invokes Linh's existing
`TrustService.rerank_candidates()` without changing Trust/R-GCN internals. Its
Tier-3 input comes only from `MutualTier1CountProvider.batch_count()`. If that
provider is absent, fails, or omits a Tier-3 candidate, that candidate is
returned as `UNKNOWN/MUTUAL_TIER1_COUNT_UNAVAILABLE`; the default policy drops
it. The boundary never fabricates a mutual-Tier-1 count.

Mentor đã xác nhận policy production: `SUSPICIOUS` phải `DROP`, không được
`DOWNRANK`. `DOWNRANK` chỉ còn là khả năng kỹ thuật của contract policy, không
phải cấu hình được phép dùng nếu chưa có một quyết định mentor/team mới kèm
policy version mới.

Vẫn cần một nguồn authoritative cho `mutual_tier1_count` trước khi candidate
Tier-3 có thể được đánh giá để admittance trong production. Khi chưa có nguồn
này, adapter trả `UNKNOWN` và policy mặc định sẽ `DROP` candidate đó.
