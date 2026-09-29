# Hướng dẫn đọc pipeline Task 1 đến Task 4

Tài liệu này giải thích pipeline hiện tại từ raw MGTAB đến kết quả classical
link prediction/PYMK. Mục tiêu là giúp đọc code, chạy lại từng bước và hiểu
đầu ra thay vì chỉ nhìn kết quả cuối.

## 1. Bức tranh tổng thể

```text
Raw MGTAB (.pt files)
        |
        v
Task 1: MGTABAdapter -> CanonicalGraph
        |
        v
Task 2: Directed/Mutual task -> leakage-safe train graph
        |
        v
Task 3: two-hop candidates -> negatives -> topology scorers
        |
        v
Task 4: binary + ranking evaluation -> CSV/report
```

Pipeline không dùng `bot` hoặc `stance` để tạo candidate hay score link. Các
labels đó chỉ được giữ ở `CanonicalGraph` để một task tương lai có thể dùng
nếu được thiết kế riêng.

## 2. Chuẩn bị để chạy

Mở PowerShell tại project root:

```powershell
cd <repository-root>
```

Project dùng môi trường `.venv`. Luôn gọi Python theo cách sau để chắc chắn
dùng đúng dependency:

```powershell
.\.venv\Scripts\python.exe --version
```

Chạy toàn bộ test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Kết quả hiện tại mong đợi:

```text
21 passed
```

## 3. Task 1 — Canonical Schema + MGTAB Adapter

### Mục đích

Task 1 tách code phía sau khỏi định dạng raw MGTAB. Thay vì Task 2–4 tự đọc
`edge_index.pt`, mọi code downstream chỉ nhận một `CanonicalGraph` thống nhất.

```text
data/raw/MGTAB/*.pt -> MGTABAdapter -> CanonicalGraph
```

### File cần đọc

```text
src/data/canonical_graph.py          Dataclass CanonicalGraph
src/data/base_adapter.py             Interface DatasetAdapter
src/data/validation.py               Kiểm tra schema tổng quát
src/data/adapters/mgtab_adapter.py   Adapter riêng cho MGTAB
scripts/validate_mgtab_adapter.py    Smoke validation
```

Raw tensors nằm tại:

```text
data/raw/MGTAB/
  edge_index.pt
  edge_type.pt
  edge_weight.pt
  features.pt
  labels_bot.pt
  labels_stance.pt
```

### CanonicalGraph là gì?

`CanonicalGraph` là Python object được tạo trong bộ nhớ, không phải file `.pt`
mới. Không có file `data/processed/canonical_graph.pt` vì Task 1 không cần
serialize graph; raw data luôn được giữ nguyên và adapter chỉ đọc.

| Field | Ý nghĩa | MGTAB hiện tại |
|---|---|---|
| `node_ids` | Canonical IDs liên tiếp `0..N-1` | 10.199 node |
| `node_features` | Feature matrix `[N,F]` | `[10199, 788]` |
| `edge_index` | COO `[2,E]`: source/destination | `[2, 1700108]` |
| `edge_type` | Relation ID mỗi edge | `[1700108]` |
| `edge_weight` | Weight mỗi edge | `[1700108]` |
| `labels` | Dictionary labels tổng quát | `bot`, `stance` |
| `relation_schema` | Metadata cho relation IDs | 7 relation |
| `metadata` | Tên dataset, version, sizes | `MGTAB`, `1.0` |

Relation schema:

```text
0 followers      1 friends       2 mention
3 reply          4 quoted        5 url
6 hashtag
```

### Chạy Task 1

```powershell
.\.venv\Scripts\python.exe scripts\validate_mgtab_adapter.py
```

Output chính:

```text
Dataset: MGTAB
Nodes: 10199
Edges: 1700108
Features: 788
Relations: 7
CanonicalGraph created successfully.
```

Hai warning sau là thông tin từ raw graph, không phải lỗi adapter:

```text
CanonicalGraph contains 205819 self-loop edge(s); none were removed
CanonicalGraph contains 561926 duplicate edge row(s); none were removed
```

### Tự inspect CanonicalGraph

Mở Python interactive:

```powershell
.\.venv\Scripts\python.exe
```

Sau đó:

```python
from src.data.adapters import MGTABAdapter

graph = MGTABAdapter("data/raw/MGTAB").transform()

print(graph.num_nodes)
print(graph.num_edges)
print(graph.num_features)
print(graph.metadata)
print(graph.relation_schema)
print(graph.labels.keys())

print(graph.node_ids[:10])
print(graph.edge_index[:, :10])
print(graph.edge_type[:10])
print(graph.node_features[:2, :10])
```

Xem edge dễ đọc:

```python
for i in range(10):
    u = graph.edge_index[0, i].item()
    v = graph.edge_index[1, i].item()
    relation_id = graph.edge_type[i].item()
    relation = graph.relation_schema[relation_id]["name"]
    print(f"{u} -> {v} | {relation}")
```

Không nên `print(graph)` toàn bộ vì graph có 1,7 triệu edge. Các notebook EDA
để xem distribution/plot raw data vẫn nằm ở `notebooks/01...` đến `06...`.

## 4. Task 2 — Task semantics và leakage-safe split

### Mục đích

Task 2 biến `CanonicalGraph` thành graph phù hợp với từng ý nghĩa link
prediction. Nó không thay đổi `CanonicalGraph` gốc.

```text
CanonicalGraph
   |-- DirectedConnectionTask --> ordered positives (u, v)
   `-- MutualConnectionTask   --> unordered positives (min(u,v), max(u,v))
```

### File cần đọc

```text
src/tasks/base_link_task.py       TaskGraph và relation resolver
src/tasks/directed_connection.py  Option A
src/tasks/mutual_connection.py    Option B
src/tasks/statistics.py           Audit graph/task
src/split/link_split.py           Deterministic split + observed graph
src/split/leakage_mask.py         Equivalent relation masking
scripts/build_link_task_stats.py  Tạo JSON statistics
scripts/validate_link_split.py    Kiểm tra split thật
```

### Option A: Directed Connection

Target là edge có hướng:

```text
u -> v
```

Ví dụ `(5,9)` và `(9,5)` là hai positive khác nhau. Target relation hiện tại
là `friends` (ID 1), được resolve qua `relation_schema`, không hard-code trong
candidate/baseline code.

### Option B: Mutual Connection Proxy

Một pair mutual chỉ tồn tại khi relation `friends` xuất hiện cả hai chiều:

```text
5 -> 9
9 -> 5
========
mutual pair = (5, 9)
```

Pair được canonicalize nên không có duplicate `(9,5)`.

### Leakage-safe split

Positive links được split deterministic với:

```text
train = 70%
validation = 15%
test = 15%
seed = 42
```

Observed train graph loại validation/test positives. Vì vậy scorer không thể
nhìn trực tiếp link cần dự đoán.

MGTAB rule được định nghĩa tập trung:

```text
friends <-> inverse-equivalent followers
```

`LeakageMasker` loại cả representation inverse từ full canonical graph khi
mask pair. Tuy nhiên candidate/scorer topology chỉ dùng target `friends`, tránh
trộn raw `followers` vào directed baseline.

### Chạy Task 2

```powershell
.\.venv\Scripts\python.exe scripts\build_link_task_stats.py
.\.venv\Scripts\python.exe scripts\validate_link_split.py
```

Output files:

```text
results/task_stats/directed_stats.json
results/task_stats/mutual_stats.json
results/task_stats/split_stats.json
```

Current task sizes:

| Metric | Directed | Mutual |
|---|---:|---:|
| Positive links/pairs | 412.575 | 85.540 |
| Active nodes | 9.418 | 9.418 |
| Mutual ratio | — | 0,414664 |

`split_stats.json` cho biết số train/val/test, số edge rows bị mask và isolated
nodes sau split. Isolated nodes được report, không bị che bằng cách sửa split.

## 5. Task 3 — Candidate generation, negatives và classical baselines

### Mục đích

Task 3 xây core classical PYMK:

```text
observed train graph
    -> two-hop candidates
    -> random/hard negatives
    -> classical score
```

### File cần đọc

```text
src/candidates/base.py             NeighborIndex
src/candidates/two_hop.py          Two-hop candidate generator
src/sampling/negative_sampling.py  Random/hard sampler
src/baselines/base.py              LinkScorer interface
src/baselines/random_score.py      Deterministic random baseline
src/baselines/common_neighbors.py  CN
src/baselines/jaccard.py           Jaccard
src/baselines/adamic_adar.py        Adamic-Adar
src/baselines/preferential_attachment.py  PA
scripts/run_baseline_smoke.py      Smoke experiment
```

### Candidate generation

Mutual task dùng neighborhood vô hướng:

```text
A -- B -- C
candidate(A) = {C}
```

Candidate generator loại source, direct/current connections và duplicates.

Directed task dùng strategy explicit:

```text
out -> out
u -> middle -> candidate
```

Nó không tự chuyển directed graph thành undirected graph.

### Negative sampling

Random negative là pair khác node nguồn, không thuộc toàn bộ known positives.
Known positives gồm cả train, validation và hidden test positives. Vì vậy edge
ẩn không thể bị lấy nhầm làm negative.

Hard negative phải thuộc two-hop candidate pool. Default `fallback="skip"`;
nếu source không có đủ hard candidate, sampler report số source thiếu thay vì
tạo dữ liệu giả.

### Baseline formulas

Với neighbor set `N(u)` và `N(v)`:

```text
Common Neighbors      |N(u) intersection N(v)|
Jaccard               intersection / union
Adamic-Adar           sum(1 / log(degree(z))) cho shared neighbor z
Preferential Attach.  degree(u) * degree(v)
Random                deterministic pseudo-random score theo seed/pair
```

Higher score luôn nghĩa là candidate tốt hơn. Directed metrics dùng out-neighbor
strategy; Mutual metrics dùng undirected neighborhood.

### Chạy Task 3 smoke test

```powershell
.\.venv\Scripts\python.exe scripts\run_baseline_smoke.py
```

Ví dụ output hiện tại:

```text
Task: directed
Source user: 0
Candidates: 1228
Top Common Neighbors:
1. 4638 score=20.000
...

Task: mutual
Source user: 0
Candidates: 4414
Top Common Neighbors:
1. 4638 score=42.000
...
```

Smoke chỉ in một node có candidate để bạn kiểm tra logic; nó không phải full
benchmark.

## 6. Task 4 — Evaluation và so sánh Directed vs Mutual

### Mục đích

Task 4 chạy matrix evaluation:

```text
2 tasks       Directed, Mutual
2 negatives   Random, Hard 2-hop
5 scorers     Random, CN, Jaccard, AA, PA
-------------------------------------------
20 experiment configurations
```

### File cần đọc

```text
src/evaluation/binary_metrics.py   ROC-AUC và Average Precision
src/evaluation/ranking_metrics.py  Precision/Recall/Hits@K, MRR, coverage
src/evaluation/evaluator.py        Candidate-based evaluator
src/evaluation/reporting.py        Markdown report renderer
scripts/run_classical_experiments.py
```

### Binary metrics

Mỗi scorer nhận positive scores và negative scores:

```text
ROC-AUC           khả năng xếp positive cao hơn negative
Average Precision  precision-recall quality, phù hợp khi class imbalance
```

Nếu chỉ có một class, code raise error rõ ràng thay vì báo metric sai.

### Ranking metrics

Với mỗi hidden positive `(u,v)`, evaluator lấy query user `u`, candidate pool
và negative/hard candidates, score rồi sort giảm dần.

| Metric | Ý nghĩa |
|---|---|
| Precision@K | tỷ lệ item relevant trong top K |
| Recall@K | tỷ lệ hidden positives được recover trong top K |
| Hits@K | query có ít nhất một positive trong top K hay không |
| MRR | nghịch đảo rank positive đầu tiên |
| Candidate coverage | hidden positives có nằm trong two-hop pool hay không |

Ranking chỉ tính các query có hidden positive nằm trong candidate pool. Positive
không nằm trong pool vẫn được tính vào `candidate_coverage`, vì ranker không thể
recover chúng theo candidate strategy hiện tại.

### Chạy Task 4

```powershell
.\.venv\Scripts\python.exe scripts\run_classical_experiments.py
```

Script chạy validation sanity trước (không tune scorer), sau đó chạy test matrix
20 cấu hình và ghi các file:

```text
results/classical_baselines/results.csv
results/classical_baselines/config.json
results/classical_baselines/validation_sanity.json
docs/directed_vs_mutual_experiment.md
```

### Vì sao không full benchmark toàn bộ test positives?

Graph có 1,7 triệu raw edge rows và candidate pool một user có thể gồm hàng
nghìn node. Script dùng sample deterministic 100 test positives mỗi task,
30 ranking negatives/query, seed 42. Các giá trị này nằm trong `config.json`.

Đây là classical experiment có thể tái lập và kiểm tra logic/runtime, không phải
production benchmark. Muốn chạy rộng hơn, chỉnh `max_positive_pairs` và
`ranking_negatives_per_query` trong `scripts/run_classical_experiments.py`, sau
đó ghi rõ config mới khi so sánh kết quả.

### Cách đọc `results.csv`

Mở file trong Excel hoặc PowerShell:

```powershell
Import-Csv results\classical_baselines\results.csv |
  Select-Object task,negative_mode,scorer,roc_auc,average_precision,recall_at_10,hits_at_10,mrr |
  Format-Table -AutoSize
```

Các column quan trọng:

```text
task, negative_mode, scorer, directed_strategy, seed
num_queries, num_positive, num_negative
roc_auc, average_precision
precision_at_5/10/20, recall_at_5/10/20, hits_at_5/10/20, mrr
candidate_coverage, avg_candidates, median_candidates
hard_negative_missing_sources, runtime_seconds
```

### Kết quả hiện tại (sample test seed 42)

| Task | Negative | Một baseline mạnh | AUC | AP | Coverage |
|---|---|---|---:|---:|---:|
| Directed | Random | Common Neighbors | 0,9110 | 0,9150 | 0,88 |
| Directed | Hard | Jaccard | 0,6969 | 0,6821 | 0,88 |
| Mutual | Random | Adamic-Adar | 0,9949 | 0,9946 | 1,00 |
| Mutual | Hard | Adamic-Adar | 0,9585 | 0,9459 | 1,00 |

Random negatives thường dễ hơn hard 2-hop negatives. Vì vậy việc metric giảm ở
hard mode là expected: hard candidates có cấu trúc gần positive hơn, gần với
quyết định PYMK hơn.

Theo sample hiện tại, Mutual có 85.540 pair, candidate coverage 100% và kết quả
hard-negative mạnh. Hướng đề xuất hiện tại là Mutual làm application task chính,
Directed giữ làm auxiliary benchmark. Đây là nhận xét dựa trên snapshot/link
reconstruction proxy, không phải kết luận về future friendship prediction.

## 7. Thứ tự chạy lại toàn pipeline

```powershell
# 1. Test tất cả unit test
.\.venv\Scripts\python.exe -m pytest -q

# 2. Task 1: adapter/canonical graph
.\.venv\Scripts\python.exe scripts\validate_mgtab_adapter.py

# 3. Task 2: task statistics + leakage-safe split
.\.venv\Scripts\python.exe scripts\build_link_task_stats.py
.\.venv\Scripts\python.exe scripts\validate_link_split.py

# 4. Task 3: candidate/baseline smoke
.\.venv\Scripts\python.exe scripts\run_baseline_smoke.py

# 5. Task 4: evaluation matrix + report
.\.venv\Scripts\python.exe scripts\run_classical_experiments.py
```

## 8. Những giới hạn quan trọng

- MGTAB là snapshot, không có temporal future-link ground truth trong pipeline này.
- Self-loop và duplicate raw edge được detect/report, không tự xóa.
- Mutual là proxy cho friendship/chat reciprocal connection, không khẳng định là friendship thật trong thế giới thực.
- Kết quả Task 4 là sample benchmark tái lập, không phải full-scale production result.
- Chưa có negative sampling nâng cao, PPR, Node2Vec, GNN, Trust/Risk/Fraud trong scope hiện tại.
