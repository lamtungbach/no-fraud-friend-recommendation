# Phase 07 Pre-Implementation Readiness Report

_Kiểm tra ngày 09/10/2026 (ICT). Phạm vi: prerequisite/readiness cho Phase 07;
không triển khai endpoint recommendation, metrics, observability hay load test._

## Verdict

**READY để bắt đầu implementation Phase 07 ở chế độ development/test.** Core
Phase 04–06, môi trường API, local active graph fixture và baseline lint đã pass.
Tuy nhiên, hệ thống vẫn **NOT READY cho runtime production-like** cho tới khi có
Trust artifact/version chính thức và nguồn authoritative cho các tín hiệu Tier-3/
dyadic safety.

**Có thể bắt đầu phần implementation Phase 07 ở chế độ development/test** với
CSV-backed `TrustServiceEligibilityProvider`; `MockTrustProvider` chỉ dùng khi
test và phải được inject tường minh. Không được đánh dấu endpoint là ready cho
production cho tới khi các blocker bên dưới được giải quyết.

## Update after Linh Trust import (09/10/2026)

`origin/main` was merged into the Phase 07 working branch at merge commit
`2cdfa4a`. It contains Linh's dyadic-safety implementation and
`data/mgtab_user_trust_profiles_v2.csv`.

The real local `TrustService` now loads **10,199** profiles from that CSV. A
smoke test through `TrustServiceEligibilityProvider` and
`TrustService.rerank_candidates()` returned `ELIGIBLE` for a Tier-1/2 profile;
this is real in-process Trust data, not `MockTrustProvider`.

The new dyadic Trust input contract includes `mutual_total_count` and
`asymmetry_penalty`. Phase 06's boundary now exposes those fields and passes
the documented Trust-schema defaults (`0`, `0.0`) until an authoritative source
exists. This keeps the adapter compatible, but it does **not** mean dyadic
signals are measured: with these defaults, no dyadic penalty is applied. The
existing fail-safe handling for Tier-3 is unchanged: without an authoritative
`mutual_tier1_count`, it becomes `UNKNOWN` and is dropped by policy.

Before production, Linh/mentor must provide:

1. a versioned Trust artifact or manifest—the imported CSV has no
   `trust_version` field; and
2. authoritative sources/lifecycle for `mutual_total_count`,
   `mutual_tier1_count`, and `asymmetry_penalty`.

Verification after the merge:

```powershell
$env:RUN_REDIS_INTEGRATION='1'
$env:REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python.exe -m ruff check src/api src/serving src/trust tests/test_api_endpoints.py tests/test_trust_module.py tests/unit/serving
.\.venv\Scripts\python.exe -m pytest -q
```

Result: **lint pass; 111 passed, 1 warning**. The warning is the existing
Starlette `TestClient` deprecation notice.

## 1. PASS / FAIL / BLOCKED / OPTIONAL

| Hạng mục | Trạng thái | Bằng chứng / ý nghĩa |
| --- | --- | --- |
| Python interpreter | PASS | `.venv\Scripts\python.exe`, Python `3.13.5` |
| FastAPI, Pydantic, Uvicorn | PASS | Cài đúng version đã pin; import `create_app()` thành công |
| pytest, httpx, Redis client, prometheus-client | PASS | Import/package check pass; `pip check` báo không có broken requirements |
| Dependency manifest | PASS | `requirements.txt` đã pin sẵn FastAPI `0.142.4`, Pydantic `2.13.4`, Uvicorn `0.34.0`, httpx, redis và prometheus-client; không cần sửa manifest |
| Artifact `phase04-smoke-v1` | PASS | Finalized artifact load được: graph version `phase04-smoke-v1`, 3 node, 2 edge |
| Active graph registry local | PASS (test fixture) | `artifacts/registry/active.json` trỏ tới artifact đã validate `phase04-smoke-v1` (3 node, chỉ dùng local smoke test) |
| Raw Top-M engine/cache | PASS | Unit suite serving và Redis integration pass; cache raw identity bao gồm version/config/user/Top-M |
| Redis local | OPTIONAL / PASS | Docker container `pymk-redis` đang Up; `docker exec pymk-redis redis-cli ping` trả `PONG` |
| Raw Top-M → Trust boundary → Safe Top-K | PASS | Phase 06 tests chứng minh raw cache độc lập Trust state/Safe Top-K không cache; CSV-backed adapter smoke pass |
| TrustService/rerank contract | PASS ở code/test | `rerank_candidates()` và adapter có test; không thay Trust/R-GCN internals |
| Trust runtime thật | PASS (local CSV) | `TrustService.is_loaded=True`, nạp 10,199 profiles từ CSV của Linh; chưa có artifact manifest/version production |
| Tier-3 mutual Tier-1 source | BLOCKED | Chưa có `MutualTier1CountProvider` authoritative; hiện fail-safe `UNKNOWN → DROP` |
| Policy `SUSPICIOUS → DROP` | PASS | `TrustPolicy` default và policy document khớp quyết định mentor |
| FastAPI recommendation route | NOT IMPLEMENTED (Phase 07 scope) | App hiện chỉ có health/Trust routes; chưa có `POST /v1/recommendations` |
| `/health/live`, `/health/ready`, `/metrics` | NOT IMPLEMENTED (Phase 07 scope) | Hiện chỉ có `/health` cũ, chưa phản ánh active graph/Trust readiness theo policy |
| API/Trust lint baseline | PASS | `ruff check src/api src/serving src/trust tests/test_api_endpoints.py tests/unit/serving` pass; B008 chỉ exempt tại FastAPI routers |
| Online request diagram | PASS | Đã thay [SeqDiagram_User_Service.png](diagram/SeqDiagram_User_Service.png): raw cache, Trust trên cả hit/miss, `SUSPICIOUS → DROP`, Safe Top-K không cache |

## 2. Environment readiness

Interpreter đang dùng:

```text
C:\no-fraud-friend-recommendation\.venv\Scripts\python.exe
Python 3.13.5
```

Các package thực tế đã kiểm tra:

```text
fastapi             0.142.4
pydantic            2.13.4
uvicorn             0.34.0
pytest              9.1.1
httpx               0.28.1
redis               6.4.0
prometheus-client   0.26.0
```

Không có dependency nào thiếu trong manifest chính thức. Không nâng Python hay
nâng cấp hàng loạt package. Nếu recreate môi trường, dùng:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

## 3. Phase 04–06 integration evidence

### Artifact và registry

`LocalArtifactStore` load được artifact finalized `phase04-smoke-v1`, do đó
format/checksum/index payload có thể được đọc. Artifact này đã được validate rồi
activate vào `artifacts/registry/active.json` cho local smoke test. Đây là graph
3-node, không phải artifact được xác nhận cho production; deployment phải activate
một graph version được duyệt bằng workflow ArtifactStore/Registry.

### Recommendation và cache

`RecommendationEngine.recommend()` vẫn là raw PYMK boundary. Cache chỉ chứa raw
Top-M; cache key gắn identity với:

```text
graph_version + retrieval_config_hash + ranking_config_hash + user_id + top_m
```

Cache payload sai/hỏng là cache miss; Redis unavailable bypass cache và graph
computation vẫn chạy. Safe Top-K không được ghi vào raw cache.

### Trust boundary

Luồng đã kiểm tra bằng unit/integration fixture:

```text
raw deterministic Top-M
→ TrustEligibilityProvider.batch_check(candidate IDs)
→ SafeTopKMerger
→ uncached Safe Top-K
```

`AllowAllTrustProvider` và `MockTrustProvider` phục vụ test/local development.
Chúng phải được inject tường minh qua composition root; production không được
fallback ngầm sang allow-all hoặc mock khi Trust runtime lỗi. Lỗi/timeout Trust
hiện trở thành `UNKNOWN` và default policy `DROP`.

## 4. Trust readiness và contract Linh

`TrustService.rerank_candidates()` nhận:

```text
target_user_id: int
candidates: list[CandidateReRankInput]
  - candidate_id: int
  - pymk_score: float >= 0
  - mutual_tier1_count: int >= 0
tier3_threshold: int = 5
```

Nó trả `SafeReRankResponse` với candidate passed/blocked, trust score, tier,
final score, `is_allowed` và reason. Phase 06 adapter gọi service này, validate
generic graph ID trước khi chuyển vào integer-only Trust contract, và không sửa
logic R-GCN/tier của Linh.

Default serving policy đã được mentor xác nhận:

| Eligibility/condition | Action |
| --- | --- |
| `ELIGIBLE` | `KEEP` |
| `SUSPICIOUS` | `DROP` |
| `BLOCKED` | `DROP` |
| `UNKNOWN`, missing profile/result, timeout/error | `DROP` |

### Giới hạn runtime production còn lại

- CSV profile đã có tại `data/mgtab_user_trust_profiles_v2.csv` và local runtime
  nạp được thành công.
- Chưa có nguồn authoritative cho `mutual_tier1_count`; Tier-3 vì vậy không
  được admit và bị drop fail-safe. Dyadic `mutual_total_count` và
  `asymmetry_penalty` cũng chưa có source runtime.
- `trust_version` ở adapter hiện là cấu hình (`trust-service-v1`), chưa được
  đọc từ lifecycle/artifact version thật của Linh.

Những điểm này không ngăn Phase 07 viết API/test với mock, nhưng chặn việc gọi
đó là Trust runtime production-ready.

## 5. Diagram và online request contract

Online diagram cũ cache Safe Top-M, trái với quyết định Phase 05–06. Bản mới
đã mô tả chính xác hai nhánh:

```text
Client
→ API validation
→ RecommendationEngine
→ GET raw PYMK Top-M cache (versioned key)

cache hit:  raw Top-M → TrustEligibilityProvider → policy merge → uncached Safe Top-K
cache miss: active graph/index → retrieval → ranking raw Top-M → SET raw cache
             → TrustEligibilityProvider → policy merge → uncached Safe Top-K

→ JSON {recommendations, graph_version, trust_version}
```

Trust chạy ở cả cache hit lẫn cache miss. Redis không chứa Safe Top-K. Diagram
hệ thống/batch lớn hơn vẫn là kiến trúc đích; PostgreSQL, Redpanda, Kubernetes
và Trust artifact lifecycle không phải implementation hoàn tất của Phase 07.

## 6. Test thực tế và lệnh tái lập

### PASS

```powershell
$env:RUN_REDIS_INTEGRATION='1'
$env:REDIS_URL='redis://127.0.0.1:6379/0'
.\.venv\Scripts\python.exe -m pytest `
  tests/unit/serving `
  tests/test_api_endpoints.py `
  tests/test_trust_module.py `
  tests/integration/test_redis_recommendation_cache.py -q
```

Kết quả sau remediation: **59 passed, 1 warning** trong 4.81 giây.
Lệnh này chạy cả Redis integration thật. Cảnh báo duy nhất là deprecation warning
từ `fastapi.testclient`/Starlette về `httpx2`; không có failure.

```powershell
.\.venv\Scripts\python.exe -m ruff check src/api src/trust src/graph src/serving src/retrieval src/ranking tests/test_api_endpoints.py tests/integration tests/unit/benchmarking tests/unit/graph tests/unit/serving tests/unit/retrieval tests/unit/ranking scripts/check_coverage.py scripts/benchmark_graph_index.py scripts/benchmark_fused_ranking.py scripts/benchmark_quality_speed.py
.\.venv\Scripts\python.exe -m pytest -q
```

Kết quả: **lint pass; 105 passed, 1 skipped, 1 warning** trong 14.75 giây.

```powershell
docker exec pymk-redis redis-cli ping
```

Kết quả: `PONG`.

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Kết quả: `No broken requirements found.`

### Lint / CI quality gate

```powershell
.\.venv\Scripts\python.exe -m ruff check `
  src/api src/serving src/trust tests/test_api_endpoints.py tests/unit/serving
```

Kết quả hiện tại: **pass**. Các import/type annotation cũ đã được chuẩn hóa; rule
`B008` được exempt có chủ đích, chỉ cho `src/api/routers/*.py`, vì FastAPI dùng
`Depends(...)` trong endpoint default. Cả `ci.yml` và `devsecops.yml` nay cài
manifest chính thức; CI chính lint cả `src/api`, `src/trust` và API tests.

Không thêm test mới trong readiness check vì suite hiện có đã cover artifact,
engine raw cache/fallback, Trust boundary, Safe Top-K, API Trust endpoints và
Redis thật. Phase 07 phải thêm test riêng cho route recommendation, live/ready,
metrics, unknown user, response contract và explicit mock/runtime modes.

## 7. File đã kiểm tra và thay đổi

### Đã kiểm tra

```text
requirements.txt
src/serving/artifact_store.py
src/serving/active_registry.py
src/serving/recommendation_engine.py
src/serving/recommendation_cache.py
src/serving/trust_boundary.py
src/trust/service.py
src/api/main.py
src/api/deps.py
src/api/routers/health.py
src/api/routers/trust.py
tests/unit/serving/
tests/test_api_endpoints.py
tests/integration/test_redis_recommendation_cache.py
```

### Đã thay đổi trong readiness check

```text
docs/diagram/SeqDiagram_User_Service.png
docs/PHASE_07_READINESS_REPORT.md
src/api/main.py
src/api/deps.py
src/api/routers/health.py
src/api/routers/trust.py
src/trust/__init__.py
src/trust/agent.py
src/trust/models.py
src/trust/schemas.py
src/trust/scoring.py
src/trust/service.py
tests/test_api_endpoints.py
ruff.toml
.github/workflows/ci.yml
.github/workflows/devsecops.yml
artifacts/registry/active.json (local runtime state; không tự stage/commit)
```

Các thay đổi code chỉ là lint/type/import và thu hẹp exception startup; không thay
đổi code Phase 04–06, thuật toán Trust/R-GCN, benchmark Phase 03 hay dependency
manifest. Active registry local được đặt rõ ràng tới smoke fixture.

## 8. Việc cần mentor/Linh xác nhận

1. Cung cấp profile runtime Trust có version rõ ràng hoặc xác nhận Trust
   dependency unavailable phải làm `/health/ready` fail thay vì phục vụ Safe
   result rỗng.
2. Chỉ rõ source authoritative và lifecycle cho `mutual_tier1_count` nếu muốn
   admit Tier-3 trong tương lai.
3. Chốt `MAX_TOP_K` cho public API; engine hiện nhận `top_k` từ caller nhưng
   chưa có giới hạn transport-level.
4. Chốt CORS allowlist/origin policy; app cũ dùng wildcard origin cùng
   credentials, không phù hợp để giữ nguyên khi public endpoint xuất hiện.
5. Xác nhận đây là một in-process Trust integration cho Phase 07 hay cung cấp
   gRPC/remote Trust service contract. Diagram dùng provider interface; code
   hiện không có gRPC contract.

## 9. Required actions before a production-like Phase 07 run

1. Cung cấp/read Trust profile artifact thật; không dùng `MockTrustProvider` hay
   `AllowAllTrustProvider` làm default production provider.
2. Chốt nguồn authoritative/lifecycle cho `mutual_tier1_count` nếu Tier-3 cần
   được admit trong tương lai.
3. Chốt `MAX_TOP_K` và CORS allowlist khi thiết kế public endpoint.
