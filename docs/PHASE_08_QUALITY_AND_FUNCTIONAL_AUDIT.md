# Phase 08 — Quality and Functional Audit

**Audit date:** 11/10/2026 (ICT)
**Scope:** code inspection, automated tests, and isolated temporary synthetic
artifacts. No production code, Trust policy, ranking, benchmark artifact,
active artifact, database, or broker was changed.

> **Current status (12/10/2026):** the detailed findings below are the
> pre-remediation baseline. The Phase 08 fixes and regression tests described
> in the remediation note are now present. Local Phase 08 is **READY**:
> pipeline tests are 23 passed / 2 intentionally skipped with 86.37% coverage,
> the full suite is 132 passed / 3 skipped, and the migrated local PostgreSQL
> integration suite is 2 passed. Production broker wiring and PostgreSQL
> contention/restart testing remain follow-up work, not prerequisites for the
> local Phase 08 handoff.

## Post-audit remediation — 12/10/2026 (ICT)

The findings P1-1 through P1-3 in this report were subsequently remediated in
the local codebase and retested: API runtime now owns the in-memory index
holder, consumes ready events, validates/warms before the swap, persists the
registry pointer, rejects non-authoritative old events through an injected
metadata `active_version` provider, and `RecommendationEngine` reads that
holder. Job execution now uses an atomic `PENDING → RUNNING` claim, so a
duplicate worker cannot fail the owner. The new local runtime v1→v2 E2E and
concurrent-worker tests pass. P1-4 (real PostgreSQL contention/restart proof),
production broker wiring, and the production Trust prerequisites remain open.

## A. Executive summary

The repository implements substantial Phase 08 components: adapter boundary,
canonical validation, immutable artifacts, in-memory job metadata, PostgreSQL
schema/repository, transactional outbox abstraction, and checksum-checked
reload. Artifact integrity and normal single-worker failure paths pass.

The end-to-end batch-to-serving path is nevertheless broken. A successful
batch job changes only pipeline metadata; it does not update the Phase 07
`ActiveGraphRegistry`. The event reloader swaps an `ActiveIndexHolder` that
`RecommendationEngine` does not use. A real isolated v1/v2 run showed that
metadata became v2 while the engine continued serving v1. A duplicate worker
can also mark an otherwise valid in-progress job FAILED.

**Historical decision (before remediation):** no observed P0 Trust bypass or
artifact-integrity defect, but Phase 08 was **NOT READY** because of activation
and concurrency defects. The current status is recorded above.

## Audit basis and phase mapping

No repository-root `AGENTS.md` exists. The current contract is
`docs/sprint2_bach/phase/PHASE_08_BATCH_METADATA_EVENTS.md`. The older Master
Plan labels batch as Phase 9, PostgreSQL as Phase 10, and Redpanda as Phase 11,
while its compact current mapping calls P8 “Batch job metadata + activation”.
This audit follows the current Phase 08 contract and records the mismatch only
as a documentation ambiguity.

Reviewed: Master Plan, Phase 04 artifact lifecycle, Phase 06 Trust boundary,
Phase 07 audit/readiness, API runtime, RecommendationEngine, pipeline modules,
migration, and relevant tests.

## B. Requirement matrix

| Requirement | Code evidence | Test / experiment evidence | Status |
|---|---|---|---|
| DatasetAdapter → CanonicalGraph and validation | `src/data/base_adapter.py`, `src/data/validation.py`, `orchestrator.py:66-79` | adapter/validation plus MGTAB/canonical scoped tests | PASS |
| Directed/mutual GraphView and CSR-like index | `src/graph/graph_view.py`, `src/serving/graph_index.py` | graph-index and artifact semantic tests | PASS |
| Immutable artifact, manifest, checksum/finalization | `src/serving/artifact_store.py` | save/load, corruption, marker/manifest tests | PASS |
| Job state machine | `metadata.py:141-173`, `orchestrator.py:66-134` | failure tests pass; duplicate-worker experiment fails | PARTIAL |
| Persist before metadata READY/active | `orchestrator.py:75-110` | normal lifecycle test | PASS, single worker |
| Atomic metadata active pointer plus outbox | `metadata.py:327-367`, migration | in-memory evidence only | PARTIAL |
| PostgreSQL metadata only | `migrations/0001_phase08_metadata.sql` | schema inspection; no live DB | BLOCKED |
| Event payload/retry/duplicate event | `events.py`, `retry_pending_events` | retry and duplicate tests pass | PASS, in-order |
| Out-of-order event safety | `events.py:89-95`, `reload.py:32-52` | v2 then v1 rolls holder back | FAIL |
| Reload validates/warm/swaps safely | `reload.py:27-52` | corrupt artifact preserves prior holder | PASS, isolated holder |
| Actual serving adopts new active graph | API reads registry; engine reads registry | v2 batch leaves registry/engine on v1 | FAIL |
| Phase 06 Trust/raw-cache safety | no pipeline changes to Trust/cache | full regression passes | PASS regression |
| Phase 08 job HTTP endpoints | current plan says HTTP may be added later; no routes | route inspection | OUT OF SCOPE |
| Structured logs and low-cardinality metrics | `orchestrator.py`, `observability.py` | code inspection | PASS locally |
| Redpanda adapter | no configured backend in repository | in-memory publisher only | OUT OF SCOPE locally / BLOCKED production |

## C. End-to-end evidence

An isolated synthetic directed graph used actual `CanonicalGraph`,
`LocalArtifactStore`, `BatchOrchestrator`, manifest validation,
`ServingIndexReloader`, and `RecommendationEngine`; only metadata/event
dependencies were explicit test doubles.

| Step | Observed result |
|---|---|
| v1, edges `0→1, 1→2` | READY; artifact persisted; metadata active=v1 |
| Manually activate existing registry | raw PYMK for user 0 returned `[2]` |
| v2, edges `0→1, 1→3` | READY; artifacts v1/v2 exist; metadata active=v2 |
| Inspect normal serving registry and engine | registry=v1; engine version=v1; candidates=`[2]` |
| Consume v2 ready event in reloader holder | holder=v2 |
| Then consume distinct older v1 event | holder rolled back to v1 |

The build/index/artifact path works. The specified path from activation to the
current recommendation service does not.

## D. Failure recovery results

| Failure scenario | Expected | Actual | Status |
|---|---|---|---|
| Invalid canonical edge | FAILED, no artifact/event | unit test confirms | PASS |
| Artifact-save exception | preserve old active | unit test confirms | PASS |
| Metadata-activation exception | preserve old active | unit test confirms | PASS |
| Corrupt artifact | reject new artifact, preserve holder | unit test confirms | PASS |
| Publish failure after activation | retain/retry outbox event | unit test confirms | PASS |
| Duplicate event | no second reload | unit test confirms | PASS |
| Older event after newer event | do not regress serving | holder v2→v1 | FAIL |
| Two workers, one job | one claim; duplicate harmless | both errors; final FAILED; no artifact | FAIL |
| PostgreSQL restart/transaction recovery | durable consistency | service unavailable | NOT TESTED |

## E. Performance results

Environment: Windows, Python 3.13.5, CPU-only local run, temporary directory,
synthetic directed graph with three outgoing edges/node. RSS is process delta,
not a peak profiler measurement.

| Nodes | Canonical edges | Build/persist/metadata | Validated load | Artifact | RSS delta | Status |
|---:|---:|---:|---:|---:|---:|---|
| 1,000 | 3,000 | 0.1540 s | 0.0073 s | 175,025 B | 5.18 MiB | READY |
| 10,000 | 30,000 | 0.2947 s | 0.0936 s | 1,687,034 B | 19.62 MiB | READY |

This is a smoke benchmark, not capacity evidence. 100k–1M workloads were not
run because there is no resource guard or peak-RSS harness. Online latency
after activation cannot be meaningfully measured until serving activation is
wired.

## F. Tests and coverage

Executed evidence:

```text
pytest [pipeline + artifact + index + retrieval + adapter/canonical/validation]
  --cov=src.pipeline --cov-report=term-missing -q
34 passed; pipeline coverage 77.65%; command failed fail-under=80.

python -m pytest -q
127 passed, 2 skipped, 1 existing Starlette/httpx deprecation warning.

python -m ruff check src/pipeline tests/unit/pipeline tests/integration/test_postgres_metadata.py
PASS

python -m bandit -r src/pipeline -q; python -m pip check
PASS; PASS
```

PostgreSQL (5432) and Redis (6379) were unreachable. No real PostgreSQL,
Redpanda, or Redis result is claimed. Whole-repository `ruff check .` remains
non-green due to 80 pre-existing findings in notebooks/earlier modules; Phase
08 scope is clean.

Missing tests: PostgreSQL transactions/concurrency, out-of-order ready events,
worker claim, actual registry/API handover, process-restart dedupe, and
large-scale/peak-RSS behavior.

## G. Critical issues

### P1-1 — Activation is disconnected from actual serving

- **Location:** `src/pipeline/orchestrator.py:66-134`,
  `src/api/runtime.py:66-76`, `src/serving/recommendation_engine.py:120`.
- **Cause:** no registry activation; reloader holder is not runtime/engine state.
- **Reproduction:** v2 READY leaves metadata=v2 and engine/registry=v1.
- **Impact:** API can serve an old graph indefinitely while metadata says new.
- **Fix/test:** adopt one serving-active authority; wire validated reload to it;
  add API v1→v2 topology/candidate E2E coverage.

### P1-2 — Duplicate worker run fails the owner job

- **Location:** `src/pipeline/orchestrator.py:66-134`,
  `src/pipeline/metadata.py:141-159`.
- **Cause:** no atomic `PENDING→RUNNING` worker claim. The duplicate raises and
  common error handling converts the running owner job to FAILED.
- **Reproduction:** block worker one after RUNNING and call `run_job` again:
  both calls `ValueError`, status=FAILED, no artifact.
- **Fix/test:** conditional atomic claim; duplicate must no-op/conflict without
  touching owner state; add concurrent test.

### P1-3 — Event reordering rolls serving back

- **Location:** `src/pipeline/events.py:89-95`, `src/pipeline/reload.py:32-52`.
- **Cause:** dedupe is only event ID; no active-version/generation ordering.
- **Reproduction:** consume v2 then v1; holder becomes v1.
- **Fix/test:** compare authoritative active version or monotonic activation
  generation before swap; test reorder and restart.

### P1-4 — PostgreSQL state transition has TOCTOU gap and no live evidence

- **Location:** `src/pipeline/metadata.py:294-307`.
- **Cause:** state is read in one transaction and updated in another, without
  old-status predicate/row lock. Concurrent writers can overwrite transitions.
- **Fix/test:** `SELECT FOR UPDATE` or conditional `UPDATE ... WHERE status`,
  row-count check, isolated PostgreSQL contention/restart migration tests.

### P2-1 — Pipeline coverage gate fails

- **Evidence:** 77.65%, below 80% configured gate.
- **Fix:** add P1 regression tests first, then PostgreSQL success/error tests.

## H. Recommended fix order

1. Make one explicit serving activation authority and wire it to the runtime.
2. Add atomic worker claiming and duplicate-safe error handling.
3. Reject stale/out-of-order lifecycle events.
4. Lock/condition PostgreSQL transitions and run isolated real DB tests.
5. Add regression/scale tests and restore the ≥80% coverage gate.

## I. Historical readiness decision

1. **Phase 09 development: NOT READY.** Graph updates do not reach the active
   recommendation service, and duplicate workers can fail legitimate jobs.
2. **Production integration: NOT READY.** P1 defects remain; PostgreSQL and
   Redpanda are not validated; Phase 07 Trust artifact/dyadic-data production
   blockers remain outside this audit.

## J. Mentor explanation

Phase 08 đã tạo được pipeline offline: adapter đổi dữ liệu thành
`CanonicalGraph`, graph/index được validate, lưu artifact bất biến có checksum,
rồi ghi metadata/outbox. Test cho thấy artifact hỏng bị từ chối, lỗi build không
phá metadata active, và publish lỗi có retry. Graph synthetic 1k/10k node build
local lần lượt khoảng 0.154/0.295 giây. Nhưng đường nối sang service đang phục
vụ chưa được cắm: v2 build xong mà engine vẫn dùng v1; thêm vào đó hai worker
chạy cùng job có thể làm job fail. Cần nối active-version authority, chặn race
worker và chống event sai thứ tự trước khi sang Phase 09. Trust/raw-cache safety
không bị thay đổi; PostgreSQL/Redpanda thật vẫn là giới hạn production.
