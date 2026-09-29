# EDA and Introduce dataset

# MGTAB EDA

---

## 1. Bức tranh lớn của project

Pipeline hiện tại:

```
MGTAB dataset
      ↓
Graph representation
      ↓
PYMK candidate generation
      ↓
Potential connections
      ↓
Trust/Fraud-aware filtering
      ↓
Future ranking / Top-K recommendations
```

PYMK trả lời:

> User nào có thể là connection tiềm năng?
> 

Trust component trả lời:

> Trong các candidate đó, account nào cần được xem xét thận trọng hơn?
> 

Trong PoC hiện tại, nhãn bot dùng để minh họa câu hỏi thứ hai. Đây chưa phải hệ thống phát hiện fraud thực tế.

---

## 2. Dataset đang dùng

Dataset là MGTAB — Multi-Relational Graph-Based Twitter Account Detection Benchmark.

**MGTAB là một bộ dữ liệu chuẩn hóa đầu tiên dựa trên đồ thị cho việc phát hiện tài khoản Twitter, tập trung vào hai nhiệm vụ chính: phát hiện bot và phân tích lập trường (stance detection).** Nó được xây dựng để khắc phục hạn chế của các benchmark trước đây vốn thiếu chất lượng gán nhãn và mối quan hệ người dùng không đầy đủ.

### Giới thiệu ngắn gọn về MGTAB

- **Quy mô:**
    - Phiên bản gốc: **10.199 người dùng** được gán nhãn bởi chuyên gia.
    - Phiên bản mở rộng (MGTAB-large): thêm khoảng **400.000 người dùng chưa gán nhãn**.
- **Loại quan hệ:** 7 loại kết nối giữa người dùng Twitter, bao gồm: *followers, friends, mention, reply, quoted, URL, hashtag*.
- **Nhiệm vụ chính:**
    - **Bot detection:** phân loại tài khoản là bot hay người thật.
    - **Stance detection:** phân loại lập trường của người dùng (ủng hộ, phản đối, trung lập).
- **Phân bố nhãn:**
    - Stance: 37% trung lập, 35.7% phản đối, 27.3% ủng hộ.
    - Bot: 73% người thật, 27% bot.
- **Đặc trưng (features):** gồm đặc trưng hồ sơ người dùng, đặc trưng tweet, và các đặc trưng quan hệ trong đồ thị.

Raw files nằm trong:

```
data/raw/MGTAB/
```

Các file chính:

| File | Ý nghĩa |
| --- | --- |
| edge_index.pt | Danh sách edge, shape (2, 1,700,108) |
| edge_type.pt | Relation type của từng edge |
| edge_weight.pt | Weight của từng edge |
| features.pt | Feature matrix của node |
| labels_bot.pt | Nhãn human/bot |
| labels_stance.pt | Nhãn stance |

Dataset hiện có:

- 10,199 labeled users;
- 1,700,108 edge rows;
- 788 feature columns;
- 7 loại relation;
- 7,451 human;
- 2,748 bot.

Mapping bot label được xác nhận từ tài liệu MGTAB:

```
0 = human
1 = bot
```

---

## 3. Notebook 01 — Data Inspection

File: notebooks/01_data_inspection.ipynb

### Mục tiêu

Notebook 01 trả lời:

> File có tồn tại, đọc được và có đúng schema không?
> 

Nó kiểm tra:

- Raw files có tồn tại không.
- Dataset path có đúng không.
- Mỗi file load lên thành object gì.
- Shape và dtype của tensor.
- Một vài sample values.
- Relation IDs và label IDs.
- Số edge có khớp với edge_type và edge_weight không.
- Node ID trong edge có hợp lệ không.
- Feature có NaN hoặc Inf không.

### Cách đọc các object

features có shape:

```
(10199, 788)
```

Nghĩa là có 10,199 node, mỗi node có 788 feature.

edge_index có shape:

```
(2, 1700108)
```

Mỗi column là một edge:

```
edge_index[:, i] = [source_node, destination_node]
```

edge_type[i] cho biết edge thứ i thuộc relation nào. edge_weight[i] là weight tương ứng.

### Relation mapping

⇒ được viết ở dạng Relation IDs : là mã số đại diện cho **edge type in graph**

| ID | Relation |
| --- | --- |
| 0 | followers |
| 1 | friends |
| 2 | mention |
| 3 | reply |
| 4 | quoted |
| 5 | url |
| 6 | hashtag |

Relation friends có ID 1 và có 412,575 edge rows.

### Kết luận của 01

Dataset load được, các tensor có shape hợp lý, edge và label cùng node space:

```
number of nodes = 10,199 
number of labels = 10,199
number of feature rows = 10,199
```

**Node**

- mỗi node(user) sẽ có 1 ID duy nhất
- Để mô hình xử lý đúng, mọi thông tin liên quan đều phải “align” theo node ID.

**Labels:** 

- mỗi node này sẽ được gán là **human/ bot và stance(pro/anti/neutral)**
- **Stance** thể hiện quan điểm thái độ lập trường với 1 vấn đề

**Feature rows**

- Mỗi node có một vector đặc trưng (feature vector).

Điều này cho phép dùng cùng node ID cho cả graph recommendation và bot/suspicious-account analysis.

---

## 4. Notebook 02 — Data Quality

### Mục tiêu

Notebook 02 trả lời:

> Dataset có lỗi dữ liệu nào cần xử lý trước khi phân tích graph hoặc train model không?
> 

### Các kiểm tra chính

#### Shape consistency

Kiểm tra:

```
len(edge_type) == number_of_edges
len(edge_weight) == number_of_edges
len(labels_bot) == number_of_nodes
len(labels_stance) == number_of_nodes
```

Các kiểm tra đều pass.

#### Valid node IDs

Node ID phải thỏa:

```
0 <= node_id < 10,199
```

Không có invalid node ID.

#### Valid labels

Các label hợp lệ:

```
bot label: 0 hoặc 1
stance label: 0, 1 hoặc 2
relation ID: 0 đến 6
```

Các kiểm tra đều pass.

#### Missing values

Feature và edge weight không có NaN hoặc Inf.

#### Duplicate edges

Khi chiếu graph về undirected pair, có:

```
791,648 duplicate undirected pairs
```

Điều này không nhất thiết là lỗi. Một cặp user có thể xuất hiện ở nhiều relation, ở cả hai chiều, hoặc nhiều lần trong raw representation.

Vì vậy cần phân biệt raw edge row và unique graph connection.

Trong PYMK baseline, graph adjacency được dùng như connection tồn tại/không tồn tại, nên duplicate được gộp khi tạo adjacency.

#### Self-loops

Dataset có:

```
205,819 self-loop rows
```

Self-loop là edge dạng (u, u). Target vẫn bị loại khỏi candidate set, nên không recommend chính nó. Tuy nhiên ở giai đoạn modeling cần quyết định rõ có giữ self-loop hay không.

### Kết luận của 02

Dataset không có lỗi schema, invalid ID hoặc missing numerical values nghiêm trọng.

Hai điểm cần document:

1. Duplicate undirected pairs.
2. Self-loops.

---

## 5. Notebook 03 — Graph EDA

File: notebooks/03_graph_eda.ipynb

### Mục tiêu

Notebook 03 chuyển câu hỏi từ:

> File có đúng không?
> 

sang:

> Graph này có cấu trúc phù hợp cho recommendation không?
> 

### Graph semantics

Raw MGTAB có nhiều relation và có hướng trong edge_index.

Để làm PYMK baseline, project tạo một undirected projection trên toàn bộ relation. Nghĩa là u → v và v → u đều được xem là một connection giữa u và v.

Graph dùng trong PYMK không chỉ là relation friends. Nó là union của followers, friends, mention, reply, quoted, url và hashtag.

Đây là assumption quan trọng cần nói với mentor.

### Density

Undirected density là tỷ lệ connection hiện có trên tổng số pair có thể có:

```
undirected density = 0.017469
```

Graph vẫn sparse so với toàn bộ node pairs. Điều này giải thích tại sao không thể xét toàn bộ non-edge cho PYMK.

### Degree distribution

| Metric | Value |
| --- | --- |
| Mean | 177.60 |
| Median | 114 |
| P90 | 401 |
| P95 | 562 |
| Max | 5,009 |

Mean lớn hơn median cho thấy degree distribution bị skew bởi high-degree users hoặc hubs.

Directed degree cũng được kiểm tra:

| Degree | Median | P90 | P95 | P99 | Max |
| --- | --- | --- | --- | --- | --- |
| In-degree | 66 | 155 | 399.2 | 655.1 | 8,330 |
| Out-degree | 83 | 178 | 418.2 | 646.0 | 8,383 |

Ý nghĩa:

- Một số user có rất nhiều connection.
- Common Neighbors có thể bị ảnh hưởng bởi hubs.
- Adamic-Adar có thể hữu ích vì giảm ảnh hưởng của common neighbor quá phổ biến.

### Connected components

Kết quả:

```
number of components = 55
largest component share = 99.47%
```

Phần lớn users nằm trong một giant component. Đây là điều tốt cho PYMK vì 2-hop candidate hoạt động trên phần lớn dataset.

Hai node ở hai component tách biệt sẽ không thể tạo candidate bằng 2-hop heuristic.

### Reciprocity

Reciprocity của directed raw graph:

```
0.554716
```

Khoảng 55.47% edge rows có reverse edge tương ứng. Raw graph có tính hai chiều đáng kể nhưng không hoàn toàn là friendship graph hai chiều.

Khi symmetrize graph để làm PYMK, direction information bị đơn giản hóa và phải được ghi rõ trong report.

### Kết luận của 03

Graph phù hợp cho PoC PYMK vì sparse, có giant component, có nhiều 2-hop structure và có degree variation để nghiên cứu ranking.

Các điểm cần kiểm soát ở giai đoạn modeling là hub effect, duplicate pairs và nhiều relation semantics.

---

## 6. Notebook 04 — PYMK EDA

File: notebooks/04_pymk_eda.ipynb

### Mục tiêu

Notebook 04 mô phỏng bước đầu của People You May Know:

> Với một target user, tạo danh sách user chưa kết nối nhưng nằm trong vùng 2-hop.
> 

### Candidate definition chính xác

Với target user u:

```
1-hop(u) = neighbors trực tiếp của u
```

Tạo 2-hop pool:

```
2-hop_pool(u)
= union neighbors(v) với mọi v thuộc 1-hop(u)
```

Sau đó:

```
candidate(u)
= 2-hop_pool(u) - 1-hop(u) - {u}
```

Đây là candidate definition được dùng thống nhất trong 04 và 05.

### Structural scores

Notebook 04 tính:

#### Common Neighbors

Số neighbor chung giữa target và candidate.

#### Jaccard

Số neighbor chung chia cho số neighbor trong union của hai node. Jaccard chuẩn hóa theo độ lớn neighborhood.

#### Adamic-Adar

Giảm trọng số của common neighbor có degree rất lớn. Một common neighbor ít phổ biến thường mang nhiều thông tin hơn một hub.

### Candidate distribution trên toàn bộ node

| Metric | Value |
| --- | --- |
| Mean candidate count | 7,218.87 |
| Median | 7,792 |
| P90 | 8,882 |
| P95 | 9,043 |
| Max | 9,529 |
| Users không có candidate | 0.53% |
| Users có candidate | 99.47% |

Graph có đủ cấu trúc để làm PYMK, nhưng candidate set rất lớn. 2-hop generation mới là bước recall-oriented candidate generation, chưa phải ranking cuối cùng.

Pipeline về sau:

```
2-hop candidates
      ↓
Structural scores
      ↓
Trust filtering
      ↓
Top-K ranking
```

---

## 7. Notebook 05 — Fraud-Aware EDA

File: notebooks/05_fraud_aware_eda.ipynb

### Mục tiêu

Notebook 05 không train fraud model. Nó trả lời:

> Candidate do PYMK sinh ra có chứa bot/suspicious account không?
> 

### Human/bot distribution

| Account Type | Count | Percentage |
| --- | --- | --- |
| Human | 7,451 | 73.06% |
| Bot | 2,748 | 26.94% |

Đây là label distribution của MGTAB, không phải tỷ lệ fraud trong thế giới thật.

### Edge mixing

Vì PYMK dùng undirected projection, edge mixing được đếm theo unique undirected pair:

| Edge Type | Count | Percentage |
| --- | --- | --- |
| Human — Human | 637,879 | 70.22% |
| Human — Bot | 226,069 | 24.88% |
| Bot — Bot | 44,512 | 4.90% |

Phần lớn connection là human-human, nhưng human-bot connection vẫn chiếm gần một phần tư unique pairs. Không được suy diễn rằng các edge này là hành vi gian lận.

### Candidate contamination

05 chỉ dùng human user làm source user. Với mỗi human user, notebook tính:

```
candidate_set(u)
bot_candidate_count(u)
bot_candidate_ratio(u)
```

Kết quả:

| Metric | Value |
| --- | --- |
| Human users analyzed | 7,451 |
| Human users không có candidate | 4 |
| Human users có ít nhất 1 candidate | 7,447 |
| Human users có bot candidate | 7,447 |
| Percentage có bot candidate | 99.95% |
| Mean bot candidate count | 1,848.53 |
| Median bot candidate count | 1,962 |
| P90 bot candidate count | 2,335 |
| Mean bot candidate ratio | 24.62% |
| Median bot candidate ratio | 24.95% |
| P90 bot candidate ratio | 26.88% |

### Ý nghĩa

Candidate contamination là đáng kể:

- Hầu như mọi human user đều gặp bot trong candidate set.
- Khoảng một phần tư candidate trung vị là bot.

Điều này cung cấp evidence rằng Trust-aware filtering có ý nghĩa trong PoC.

Tuy nhiên, kết quả này không chứng minh bot candidate là fraud candidate. Nó chỉ cho thấy nếu hệ thống muốn hạn chế account đáng ngờ, bot label có thể minh họa bước filtering.

Candidate set cũng rất lớn:

```
mean = 7,424
median = 7,901
```

Vì vậy hệ thống sau này cần ranking, threshold, top-K hoặc candidate pruning.

---

## 8. Notebook 06 — EDA Summary & Dataset Decision

File: notebooks/06_eda_summary.ipynb

### Mục tiêu

Notebook 06 tổng hợp:

- dataset overview;
- data quality;
- graph structure;
- PYMK feasibility;
- fraud-aware relevance;
- limitations;
- dataset decision.

Nó đọc các kết quả candidate analysis được lưu tại:

```
results/eda_05/
```

Các file gồm:

- candidate_report.csv;
- aggregate_report.csv;
- edge_mixing.csv;
- label_distribution.csv.

### Dataset decision

MGTAB được chọn làm dataset chính cho PoC vì:

1. Có graph user/account.
2. Có nhiều loại relationship.
3. Có đủ structure để sinh 2-hop candidate.
4. Có nhãn human/bot để làm suspicious-account proxy.
5. Recommendation và Trust có cùng node space.
6. Có quy mô đủ lớn để minh họa vấn đề thực tế hơn toy graph.

Đây là quyết định có điều kiện:

- MGTAB phù hợp cho PoC;
- không phải financial fraud dataset;
- bot label không phải fraud ground truth;
- graph projection có thể làm mất direction semantics.

---