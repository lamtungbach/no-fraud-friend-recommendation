# Current State Checkpoint — Sprint 2 / Bách PYMK

_Cập nhật lần cuối: 08/10/2026 (ICT). Phần Phase 00 là lịch sử; checkpoint Phase 01 hiện hành nằm ở mục 8._

Tài liệu này là checkpoint trước khi bắt đầu **PHASE 01 — Bounded Two-Hop Retrieval**. Nó ghi nhận trạng thái repository thực tế, kết quả đã xác minh và các bước cần hoàn tất trước khi sang phase tiếp theo.

## 1. Git và tích hợp DevSecOps

- Nhánh đang dùng: `main`.
- `main` đã được fast-forward đến commit `b4904ef` từ `origin/main`.
- Phần DevSecOps của Linh đã có trong local repository, bao gồm:
  - `.github/workflows/devsecops.yml`;
  - `.pre-commit-config.yaml`;
  - cập nhật dependency, ignore rule và CI test behavior khi thiếu raw MGTAB.
- Khi pull, có một conflict tại `src/data/adapters/mgtab_adapter.py`. Conflict đã được giải quyết theo hướng giữ local loader an toàn:

  ```python
  torch.load(path, map_location="cpu", weights_only=True)
  ```

  Không còn conflict marker hoặc unmerged path.

## 2. Trạng thái PHASE 00

PHASE 00 đã được thực hiện và xác minh, nhưng commit đã được **cố ý gỡ ra** để người dùng tự thực hành quy trình Git. Vì vậy các file Phase 00 hiện là thay đổi local **chưa stage** trên `main`.

Nội dung Phase 00 cần được stage/commit riêng:

```text
.coveragerc
.github/workflows/ci.yml
requirements-dev.txt
scripts/benchmark_graph_index.py
scripts/check_coverage.py
src/graph/
src/retrieval/
src/serving/
tests/unit/
artifacts/sprint2/part1/graph_index_benchmark.json
artifacts/sprint2/part1_test_summary.txt
```

Các phần này tạo boundary serving Part 1:

```text
CanonicalGraph
  -> GraphView
  -> ServingGraphIndex
  -> exact, unbounded two-hop retrieval
```

Không có candidate cap, fused ranking, Redis, Trust/Fraud integration, FastAPI hay tính năng Phase 01+ trong phần này.

## 3. Kết quả kiểm chứng PHASE 00

| Hạng mục | Kết quả |
|---|---|
| Regression suite | `31 passed` |
| Unit test Part 1 | `10 passed` |
| Exact two-hop parity với reference | Pass |
| Tổng coverage Sprint 2 Part 1 | `92.86%` |
| `src/graph` coverage | `88.57%` |
| `src/serving` coverage | `96.97%` |
| `src/retrieval` coverage | `100.00%` |
| Ruff | Pass |
| Bandit | Pass |
| pip-audit | Pass — không có known vulnerabilities |
| Gitleaks | Chưa chạy local: binary không có; Docker fallback bị environment từ chối |

Benchmark reproducible đã sinh tại:

- `artifacts/sprint2/part1/graph_index_benchmark.json`
- `artifacts/sprint2/part1_test_summary.txt`

Benchmark dùng synthetic directed graph, seed 42, 1.000 nodes, 4.984 unique edges và 100 query; artifact chứa index size, memory estimate, latency p50/p95/p99 và thống kê candidate count. Đây chỉ là smoke benchmark, **không phải** bằng chứng production performance.

## 4. Chi tiết ổn định Part 1

- `GraphView` có directed view và reciprocal-only mutual view tường minh, không hard-code MGTAB vào serving logic.
- `ServingGraphIndex` dùng adjacency sắp thứ tự, deterministic; có `neighbors`, `degree`, `has_edge`, external/internal mapping và metadata node/edge.
- `internal_to_external(-1)` hiện raise `KeyError` thay vì vô tình trả về node cuối theo Python negative indexing.
- Exact two-hop retrieval loại query user, direct neighbor, duplicate và có implementation reference để kiểm tra parity.
- Sprint 1 leakage-safe semantics không bị thay đổi.

## 5. Những thay đổi local ngoài PHASE 00

Working tree còn có thay đổi/asset khác không được đưa vào phạm vi commit Phase 00, như notebook EDA, adapter MGTAB, evaluator, negative sampling, docs/diagram, PDF notebook và artifact khác.

Khi stage Phase 00, phải dùng danh sách file tường minh ở mục 2. Không dùng `git add .`.

Hai stash an toàn vẫn được giữ từ thao tác pull trước đó. Không cần apply hoặc drop chúng trước khi xác nhận mọi thay đổi local hiện hữu đã được commit đúng nơi.

## 6. Việc cần làm trước PHASE 01

1. Tạo branch riêng từ `main`, ví dụ `bach/phase-00-stabilize-part1`.
2. Stage đúng các file Phase 00 ở mục 2.
3. Kiểm tra bằng `git diff --cached --stat` và đảm bảo không lẫn notebook/docs/logic Sprint 1.
4. Commit với message đề xuất:

   ```text
   chore(sprint2): stabilize graph index part1
   ```

5. Push branch và mở PR vào `main`; chỉ merge sau review.
6. Khi Phase 00 đã có commit sạch, đọc `PHASE_01_BOUNDED_RETRIEVAL.md` và chỉ triển khai bounded retrieval theo đúng contract/test của Phase 01.

## 7. Invariants phải giữ khi sang PHASE 01

- `CanonicalGraph` vẫn là dataset-independent boundary.
- Không hard-code MGTAB/relation ID vào engine serving.
- Không để validation/test positives lọt vào observed graph dùng cho candidate/scoring.
- Retrieval phải local-neighborhood, deterministic và không global scan mọi node.
- Candidate cap chỉ được thêm cùng metrics về truncation, coverage và quality theo Phase 01/03.
- Không triển khai fused ranking, Trust/Fraud model, Redis, FastAPI hoặc bất kỳ Phase sau nào khi đang làm Phase 01.

---

## 8. Checkpoint hiện hành — sau PHASE 01

### Git và tiến độ

- **Phase 00:** đã merge vào `main` tại `f9c9dc2` sau khi tất cả CI checks pass.
- CI đã được ổn định bằng hai fix: `pywinpty` chỉ cài trên Windows và các seeded experimental RNG có giải thích `# nosec B311`.
- **Phase 01:** đã hoàn thành cục bộ trên branch `bach/phase-01-bounded-retrieval`.
- Commit Phase 01: `2d1375a feat(retrieval): add bounded two-hop candidates`.
- Commit này sẵn sàng được push và mở PR vào `main`; Phase 02 chỉ bắt đầu sau khi PR Phase 01 pass, review và merge.

```powershell
git push --set-upstream origin bach/phase-01-bounded-retrieval
```

### Chức năng Phase 01

Phase 01 thêm deterministic bounded two-hop retrieval:

```text
ServingGraphIndex
  -> bounded two-hop expansion
  -> candidate IDs + RetrievalStats
```

Các file thuộc Phase 01:

```text
src/retrieval/bounded.py
src/retrieval/__init__.py
tests/unit/retrieval/test_bounded_two_hop.py
scripts/benchmark_bounded_retrieval.py
artifacts/sprint2/phase01/bounded_retrieval_benchmark.json
```

API chính:

```python
RetrievalConfig(
    first_hop_cap: int | None = None,
    second_hop_cap: int | None = None,
    candidate_cap: int | None = None,
    strategy: str = "deterministic",
    seed: int = 42,
)

retrieve_bounded_two_hop_candidates(user_id, graph, config)
    -> RetrievalResult(candidate_ids, stats)
```

### Cap semantics đã chốt

| Cap | Thời điểm áp dụng | Quy tắc |
|---|---|---|
| `first_hop_cap` | Trước expansion | Dùng tối đa N first-hop đầu tiên theo sorted deterministic adjacency. |
| `second_hop_cap` | Cho từng first-hop đã chọn | Expand tối đa N neighbor đầu tiên của mỗi first-hop. |
| `candidate_cap` | Sau bounded collection | Giữ tối đa N candidate theo deterministic discovery order. |

Candidate luôn loại query user, direct neighbor và duplicate. `truncated=True` khi bất kỳ cap nào thực sự loại adjacency entry hoặc candidate. Candidate order chỉ là deterministic traversal order, không phải score/rank. Khi cả ba cap là `None`, membership khớp exact/unbounded reference Phase 00.

### Kết quả kiểm chứng Phase 01

| Hạng mục | Kết quả |
|---|---|
| Full regression | `40 passed` |
| Tổng relevant coverage | `95.15%` |
| `src/graph` coverage | `88.57%` |
| `src/serving` coverage | `96.97%` |
| `src/retrieval` coverage | `100.00%` |
| Ruff | Pass |
| Bandit | Pass |
| pip-audit | Pass — no known vulnerabilities |
| Unlimited parity | Pass |
| Determinism / cap / exclusion tests | Pass |

Test coverage gồm isolated user, degree-one user, duplicate path, direct neighbor, self-return, từng cap, cap kết hợp, cap lớn hơn neighborhood, invalid config, deterministic repeat và unlimited parity.

### Benchmark evidence

Artifact: `artifacts/sprint2/phase01/bounded_retrieval_benchmark.json`.

- Synthetic directed graph, seed 42, 1.000 nodes, 4.984 unique directed edges, 100 query.
- Demonstration caps: first-hop 4, second-hop 8, candidate 16.
- Local latency: p50 khoảng 0,009 ms; p95 khoảng 0,011 ms; p99 khoảng 0,014 ms.
- Mỗi query có degree, candidates returned, truncation và latency.

Đây là reproducible microbenchmark, không phải lựa chọn cap cuối cùng hoặc production-performance claim. Quality-speed trade-off thuộc Phase 03.

### Điều kiện trước PHASE 02

1. Push/merge PR Phase 01 vào `main`.
2. Fast-forward local `main`, rồi tạo branch mới, ví dụ `bach/phase-02-fused-ranking`.
3. Đọc `AGENTS.md`, `PHASE_02_FUSED_RANKING.md` và chỉ phần Master Plan liên quan.
4. Giữ nguyên semantics bounded retrieval và Sprint 1 leakage-safe behavior.
5. Phase 02 chỉ làm fused CN/AA/Jaccard/PA và deterministic Top-M; không làm cache, API hoặc Trust/Fraud.

---

## 9. Current checkpoint — after PHASE 02

### Git and scope

- **Phase 02:** completed on `bach/phase-02-fused-ranking` at commit
  `1369e28 feat(ranking): add fused topology scoring and deterministic top-m`.
- Scope was limited to fused topology ranking, deterministic Top-M, tests,
  benchmark evidence, and ranking coverage/CI integration. No cache, API,
  Trust/Fraud, deployment, or PHASE 03 work was added.

### Phase 02 contract

```text
bounded two-hop RetrievalResult
  -> fused CN / AA / Jaccard / PA scoring
  -> deterministic Top-M (score DESC, candidate_id ASC)
```

- `src/ranking/topology.py` computes all four classical topology scores from
  the same configured `ServingGraphIndex` graph semantics.
- Directed scoring preserves Sprint 1 outbound-neighbor semantics; mutual
  scoring uses the mutual graph view without reinterpretation.
- Zero-degree, Jaccard zero-denominator, AA degree-one, empty-pool, and
  non-finite-score cases are covered.

### Verification and evidence

| Item | Result |
|---|---|
| Full regression | `51 passed` |
| Total measured coverage | `94.69%` |
| `src/ranking` coverage | `96.00%` |
| Directed and mutual Sprint 1 scorer parity | Pass |
| Unlimited retrieval + scoring parity | Pass |
| Ruff / Bandit / pip-audit | Pass |

Benchmark evidence: `artifacts/sprint2/phase02/fused_ranking_benchmark.json`.
It records reproducible synthetic directed measurements with separate
retrieval, scoring, Top-M, and total latency percentiles. It is a local
microbenchmark only, not a production-performance claim.

### Preconditions for PHASE 03

- Keep `CanonicalGraph` as the dataset-independent boundary.
- Build every evaluation graph from leakage-safe observed topology; do not
  place validation/test positives in the serving graph.
- Measure the real bounded candidate pool and include queries whose held-out
  positive is missed in overall ranking metrics.
- Do not change ranking formulas merely to improve benchmark scores.
