# Phase 07 — Full Implementation Audit & Readiness Check

**Audit date:** 10/10/2026 (ICT)
**Scope:** Audit only. No business logic, Trust policy, ranking algorithm, benchmark, or Phase 08 code was changed.
**Audit target:** current working tree at `C:\no-fraud-friend-recommendation`.

## Audit basis and naming note

No repository-root `AGENTS.md` was found. The authoritative implementation plan used for this audit is `docs/sprint2_bach/phase/PHASE_07_FASTAPI_OBSERVABILITY_TESTS.md:1-50`.

There is a documentation naming mismatch: the older master plan calls FastAPI and observability **“PHASE 8”** (`docs/sprint2_bach/00_MASTER_PLAN.md:893-957`), while the repository's current plan calls the same scope **Phase 07**. This report uses the current repository name and does not reinterpret Phase 08 batch/event scope.

Phase 04–06 were checked against `PHASE_04_VERSIONED_ARTIFACTS.md`, `PHASE_04_ARTIFACT_LIFECYCLE.md`, `PHASE_00_TO_05_SYSTEM_MAP.md`, and `PHASE_06_TRUST_BOUNDARY.md`. `docs/PHASE_07_READINESS_REPORT.md` is a pre-implementation readiness report: its statements that the API route, health, and metrics are “NOT IMPLEMENTED” are now stale and were not used as current implementation evidence.

## A. Executive summary

**Verdict: PARTIALLY COMPLETE.**

The primary local serving path works. FastAPI starts under Uvicorn; it registers `POST /v1/recommendations`, liveness, readiness, and Prometheus metrics; and the route delegates to `RecommendationEngine.recommend_safe()` rather than reimplementing retrieval/ranking. Local CSV-backed Trust loads, and real HTTP calls reach a safe response.

Phase 07 is not ready for sign-off or production integration. The highest-priority issue is that explicit `mock`/`allow-all` providers can report ready in `development`, although fake Trust must not make a non-test runtime ready. Redis-real integration also failed in this audit because the local endpoint refused connections. Observability, error response consistency, coverage scope, and current-status documentation remain partial.

## B. Requirement matrix

| Hạng mục | Yêu cầu | Trạng thái | File/code chứng minh | Test/evidence | Còn thiếu |
|---|---|---|---|---|---|
| FastAPI entrypoint | Factory, import, Uvicorn local | PASS | `src/api/main.py:14-79` | Uvicorn TCP smoke started/stopped cleanly | — |
| Router registration | Health, Trust, recommendations registered | PASS | `src/api/main.py:42-44`; `src/api/routers/__init__.py:4-8` | HTTP endpoints reachable | — |
| Thin transport layer | Route only validates/orchestrates/serializes | PASS | `src/api/routers/recommendations.py:24-64` | Delegates to `engine.recommend_safe()` at line 41 | — |
| Request validation | `user_id`, positive/config-bounded `top_k`, forbid extra fields | PASS | `src/api/schemas.py:8-12`; `src/api/routers/recommendations.py:31-37` | API tests; real `top_k=0` returned 422 | — |
| Safe response | Safe Top-K plus graph/trust/policy/cache metadata | PASS | `src/api/schemas.py:15-30`; router `:55-63` | API tests and real HTTP response | No automated real-engine non-empty Safe Top-K E2E fixture |
| Unknown/empty results | 404 unknown; empty list valid | PASS | router `:48-53` | Unknown returned 404; valid smoke user returned empty safe list | — |
| Active graph lifecycle | Resolve active version and validate artifact/index | PASS | `src/api/runtime.py:40-60`; engine `:120-182` | Ready reports `phase04-smoke-v1`; core tests pass | Active graph is local smoke fixture only |
| Raw cache and fallback | Versioned raw Top-M; Redis failure computes graph result | PASS (fallback) / FAIL (Redis-real audit) | engine `:120-182,228-265`; cache `:70-125` | Redis refusal fell back safely; Redis suite had 4 setup errors at `tests/integration/test_redis_recommendation_cache.py:36` | Restore Redis and rerun |
| Trust after hit/miss | Trust always follows raw result; Safe Top-K never cached | PASS in code/unit tests | engine `:201-226`; trust boundary `:329-402` | Existing unit/integration source covers raw hit calling Trust | Redis-backed variant not runnable in audit |
| Local real Trust | CSV `TrustServiceEligibilityProvider`, no silent fallback | PASS (local only) | `src/api/runtime.py:73-96`; `src/serving/trust_boundary.py:194-323` | CSV service loaded; full tests passed | No versioned production artifact/manifest |
| Trust timeout/error | No raw candidate admission on provider failure | PASS | trust boundary `:348-357` | Forced timeout returned 200 with `recommendations=[]`, `trust_version="unavailable"` | Failure is not logged with useful context |
| Fake-provider readiness | Mock/allow-all must not make non-test ready | FAIL | `src/api/runtime.py:53-60,90-93` | Development mock/allow-all has no readiness reason | P0 gate required |
| Health | Liveness and graph/Trust readiness | PASS with P0 limitation | `src/api/routers/health.py:17-52` | Live/ready 200; no-active-graph returned 503 | Fix fake-provider readiness |
| Required Phase metrics | Recommendation, cache, retrieval count/truncation, Trust, graph version | PASS | `src/api/observability.py:16-28,57-84` | `/metrics` changed after a real request; no raw-ID labels | Metric names differ from older master plan but satisfy current-plan intent |
| HTTP/retrieval/ranking latency | Audit asks HTTP metrics and individual retrieval/ranking timings | PARTIAL | `src/api/observability.py:16-84` | End-to-end recommendation and Trust latency exist | No HTTP middleware metrics; no retrieval/ranking latency histograms |
| Structured logging | Structured events and important failures | PARTIAL | `src/api/observability.py:67-84` | JSON success/error helpers exist | Provider error becomes a safe empty result, but has no failure log event; no request/correlation ID contract |
| Error consistency | Opaque, consistent API errors | PARTIAL | router `:48-53` | Forced unexpected `TypeError` returned generic 500 without traceback | Response is `text/plain`, not a JSON error envelope; no explicit global handler |
| Test/coverage gate | Coverage >=80% where policy applies | PARTIAL | `.coveragerc:3-7`; API tests | Core configured scope 88.84%; audit API+Trust run 80% | CI excludes `src/api`/`src/trust`; runtime 76%, observability 78%, trust/models 22% |
| E2E HTTP | Start service, call contract, stop cleanly | PASS (minimal) | `src/api/main.py:72-79` | TCP Uvicorn smoke passed live/ready/recommendation/metrics | Persist a non-empty fixture E2E test |
| Load smoke | Reproducible count/concurrency/percentiles/error/cache mix | PARTIAL | `scripts/load_test_api.py:54-109` | 20 requests/concurrency 4: 20 success, p95 391 ms, external 12.68 RPS | Script itself omits duration/RPS; Redis unavailable, so 20 misses |
| Security/static | Ruff, Bandit, pip-audit, gitleaks | PARTIAL | plan `:43`; `requirements-dev.txt` | Ruff/Bandit/pip check pass | pip-audit network blocked; gitleaks unavailable |
| Phase boundary | No batch/events/K8s/Postgres implementation | PASS | plan `:17,48-50` | Source tree review | Correctly remains later-phase work |

## C. Critical issues

### C1. P0 — false-ready state with mock/allow-all outside test

`ApiSettings` permits `mock` and `allow-all` in `development` (`src/api/config.py:29-39`). `ApiRuntime.readiness()` rejects non-CSV only when environment is exactly `production` (`src/api/runtime.py:53-55`). A development/staging-like process with an active graph and `TRUST_PROVIDER=mock` can therefore report ready without real Trust.

This is not silent fallback—selection is explicit—but it violates the audit requirement that mock must not create a false-ready state outside test. Deployment automation or an operator could regard an unsafe Trust configuration as healthy.

### C2. P0 for production integration — readiness does not encode known Trust prerequisites

Production CSV Trust can return ready once loaded even when its version is deliberately `unversioned-csv-no-manifest` (`src/api/config.py:22,66`) and no authoritative Tier-3/dyadic source exists. The service safely drops unavailable Tier-3 candidates, but cannot be presented as a production-integrated Trust runtime until Linh/mentor supplies a versioned artifact/manifest and signal lifecycle.

### C3. P1 — Redis-real integration is not reproducible now

With `RUN_REDIS_INTEGRATION=1` and `REDIS_URL=redis://127.0.0.1:6379/0`, all four Redis integration tests failed during fixture `client.ping()` with `ConnectionRefusedError [WinError 10061]`. Docker inspection was also blocked by denied access to `C:\Users\Admin\.docker\config.json`.

Fallback behavior is correct in the observed HTTP run: requests continued with `raw_cache_hit=false`; Redis did not affect liveness/readiness. Actual Redis correctness is nevertheless not PASS for this audit environment.

### C4. P1 — unexpected errors lack a consistent JSON API contract

The router maps `KeyError`, `RuntimeError`, and `ValueError`, but a forced `TypeError` returned `500 text/plain; charset=utf-8` with `Internal Server Error`. No traceback was exposed, which is good; however, callers do not receive the JSON-shaped error response used elsewhere. There is no explicit global exception handler/logging shown in `src/api/main.py`.

### C5. P1 — observability is incomplete for operations

The code records end-to-end recommendation and Trust latency, but lacks HTTP request middleware metrics and retrieval/ranking latency histograms. `SafeTopKMerger` converts provider exceptions to safe empty output; the counter increments through `ObservedTrustEligibilityProvider`, but the event is logged as successful empty recommendation rather than a Trust failure.

## D. Missing components and recommended remediation

| Priority | Vấn đề / ảnh hưởng | File đề xuất | Cách sửa đề xuất | Cách test sau sửa |
|---|---|---|---|---|
| P0 | Mock/allow-all can report ready outside `test` | `src/api/runtime.py`, API tests | Add readiness reason for fake provider unless `environment == "test"`; preserve explicit test injection | Development fake provider with valid graph => `/health/ready` 503 |
| P0 (production) | Trust artifact/version and dyadic/Tier-3 source absent | `src/api/config.py`, `src/api/runtime.py`, external Trust handoff | Agree manifest/source contract; require it for production readiness | Production without approved contract => 503; approved fixture => 200 |
| P1 | Redis runtime unavailable; no real cache proof | local Redis/Docker and `tests/integration/test_redis_recommendation_cache.py` | Restore documented Redis startup/configuration and rerun opt-in suite | Four tests pass; actual HTTP miss then hit still invokes Trust |
| P1 | Plain-text unhandled 500 | `src/api/main.py`, router, tests | Add bounded global JSON exception handler and server-side error logging without raw IDs | Forced internal error => opaque JSON 500, no traceback, one error metric/log |
| P1 | Incomplete timings and Trust-failure logging | observability/engine/API tests | Add bounded HTTP metrics; record existing engine `LatencyBreakdown`; log Trust failure | Scrape metrics before/after; verify metrics move and labels have no IDs |
| P1 | CI coverage omits API/Trust | `.coveragerc`, API/runtime tests | Agree source set/threshold; test unavailable Trust, invalid artifact, Redis error, global handler | CI report includes API; agreed policy threshold passes |
| P1 | No automated non-empty real-engine TCP E2E | new integration test only | Run Uvicorn with small graph/index + explicit mock Trust and assert safe candidate semantics | TCP test asserts candidate, ordering, metadata, no self/direct/duplicate |
| P2 | Load JSON has no duration/RPS; no dedicated concurrent cache correctness test | `scripts/load_test_api.py`, tests | Emit duration/throughput; run with Redis and preserve artifact | Output has RPS/cache hit+miss; concurrent run error-free |
| P2 | Lifespan cleanup/metric label retention and stale readiness document | `src/api/main.py`, metrics, `docs/PHASE_07_READINESS_REPORT.md` | Define owned-client cleanup/retention; supersede old readiness document | Factory start/stop and documentation review |

## E. Test evidence

All commands were run on 10/10/2026 from `C:\no-fraud-friend-recommendation` using `.venv\Scripts\python.exe`.

| Command / procedure | Actual result | Dependency/runtime notes |
|---|---|---|
| `python -m ruff check src/api src/serving src/trust tests/test_api_endpoints.py tests/test_api_recommendations.py tests/integration tests/unit/serving scripts/load_test_api.py` | PASS | Phase 07 static scope |
| `python -m pytest -q` | **117 passed, 1 skipped, 1 warning** | Existing Starlette/TestClient deprecation warning |
| `python -m pytest -q --cov` | PASS, **88.84%** | `.coveragerc` only measures graph/serving/retrieval/ranking; target 80% reached |
| API/Trust audit coverage command | **18 passed, 80%** | `pytest ... --cov=src.api --cov=src.trust --cov-fail-under=0`; not current CI scope |
| Redis integration command with env | **4 errors** | Endpoint refused connection during `client.ping()` |
| Uvicorn TCP smoke | PASS | Live/ready 200, graph `phase04-smoke-v1`, recommendation 200, metrics changed |
| Error-path smoke | PASS / finding | Missing graph => 503; forced Trust timeout => safe empty 200; forced `TypeError` => plain-text 500 |
| Load smoke, 20 requests / concurrency 4 | PASS (smoke only) | CSV Trust; Redis unavailable; 20/20 200, 0% error, p50 257 ms, p95 391 ms, p99 392 ms, external 12.68 RPS, all raw-cache misses |
| `python -m bandit -q -r src/api src/serving src/trust` | PASS | Existing reviewed `# nosec B104` only |
| `python -m pip check` | PASS | No broken requirements |
| `python -m pip_audit` | NOT TESTED | PyPI network access denied: `WinError 10013` |
| `gitleaks detect --no-git` | NOT TESTED | Binary unavailable; Docker fallback blocked by Docker-config access denial |

Configured coverage does not prove API coverage because `.coveragerc:3-7` excludes it. The direct audit run found: `src/api/runtime.py` 76%, `src/api/observability.py` 78%, `src/trust/agent.py` 69%, `src/trust/models.py` 22%, and `src/trust/scoring.py` 71%.

## F. Phase 08 readiness

### Development checklist

- [x] FastAPI route delegates to Phase 05/06 core.
- [x] Local graph/CSV Trust HTTP smoke works.
- [x] Safe Trust-timeout behavior is demonstrated.
- [x] No Phase 08 batch/event/K8s/Postgres code was added.
- [ ] **P0:** fake Trust must not make a non-test runtime ready.
- [ ] Redis integration must pass after Redis is available, or be documented as a reproducible environment blocker.
- [ ] The stale readiness report needs superseding status documentation.

**Conclusion — Phase 08 development: NOT READY.** Fix and test the P0 readiness condition before treating Phase 07 as an approved service boundary and starting Phase 08 implementation.

### Production-integration checklist

- [ ] Versioned authoritative Trust artifact/manifest.
- [ ] Authoritative lifecycle/source for `mutual_tier1_count`, `mutual_total_count`, and `asymmetry_penalty`, or an approved policy that readiness remains false without them.
- [ ] Production readiness gate for those prerequisites.
- [ ] Approved active graph artifact, not only `phase04-smoke-v1`.
- [ ] Redis operational test or documented optional-cache posture.
- [ ] Approved `MAX_TOP_K`, CORS allowlist, and Trust runtime contract.
- [ ] Security scans runnable in target environment.

**Conclusion — production integration: NOT READY / BLOCKED.** The primary blockers are missing authoritative Trust assets/decisions, not an algorithm change request.

## G. Recommended fix order

1. **Gate mock/allow-all readiness outside test (P0).** It prevents unsafe configuration from appearing healthy and is contained to Phase 07 configuration.
2. **Obtain and encode the Trust production contract (P0/blocker).** Truthful production readiness requires a manifest and authoritative dyadic/Tier-3 decision.
3. **Restore Redis and rerun real integration tests (P1).** Fallback is valid but cache behavior needs live evidence.
4. **Add consistent exception handling and complete observability (P1).** Operators and clients need opaque JSON errors, segment timings, and Trust-failure logs.
5. **Close evidence/documentation gaps (P1/P2).** Add non-empty fixture E2E, include API/Trust coverage by policy, self-contain load results, run blocked security scans, and supersede stale documentation.

## Architecture consistency conclusion

The online path is consistent with Phase 04–06:

```text
FastAPI transport
→ RecommendationEngine raw Top-M
→ active versioned artifact + versioned raw cache
→ TrustEligibilityProvider
→ SafeTopKMerger
→ uncached Safe Top-K response
```

Evidence: `src/api/routers/recommendations.py:24-64`, `src/serving/recommendation_engine.py:99-226`, and `src/serving/trust_boundary.py:329-402`. No route-level graph traversal, ranking formula, Redis-key construction, or Trust-policy rewrite was found. PostgreSQL, Redpanda, batch lifecycle, and Kubernetes remain designed/planned for later phases and are out of scope for this audit.

## Post-audit update — 11/10/2026

This update supersedes the earlier Redis and fake-provider-readiness findings
where they conflict with the evidence below.

- **Resolved P0 — fake Trust readiness:** `src/api/runtime.py` now adds
  `non_test_trust_provider` whenever the configured provider is not CSV and
  `API_ENVIRONMENT` is not `test`. Therefore explicit `mock` and `allow-all`
  remain available for tests, but cannot make development or production-like
  readiness green.
- **New test evidence:** `tests/test_api_recommendations.py` now parameterizes
  both fake providers. The focused API suite passed **12 tests**: each fake
  provider returns 503 at `/health/ready` in development and 200 only in test
  mode. Ruff passed for the changed scope.
- **Resolved local Redis environment blocker:** after starting `pymk-redis`,
  `tests/integration/test_redis_recommendation_cache.py` passed **4 tests**
  against `redis://127.0.0.1:6379/0`.

### Revised readiness conclusion

- **Phase 08 development: READY.** The previously blocking Phase 07 local
  readiness guard and Redis-real integration evidence now pass.
- **Production integration: NOT READY / BLOCKED.** The versioned Trust
  artifact/manifest and authoritative Tier-3/dyadic signal lifecycle still
  require Linh/mentor decisions. The P1 observability, error-envelope,
  non-empty E2E, coverage-scope, and security-tool evidence items remain
  recommended Phase 07 hardening work.
