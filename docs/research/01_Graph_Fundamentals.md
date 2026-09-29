# 01. Graph Fundamentals

## Bản chất bài toán

Bài toán **People You May Know (PYMK)** có thể được nhìn dưới góc độ **Link Prediction**:

> Biểu diễn mạng xã hội thành một **graph**, sau đó khai thác cấu trúc của graph để tìm những **non-edge có tiềm năng trở thành edge**.

Ở giai đoạn này, mục tiêu chính là hiểu cách biểu diễn mạng xã hội bằng graph và cách sinh ra tập candidate. Phần tính score chi tiết sẽ được học sau.

---

## 1. Graph \(G=(V,E)\)

Một graph được biểu diễn bởi:

$$
G=(V,E)
$$

Trong đó:

$$
V=\{v_1,v_2,\ldots,v_n\}
$$

là tập các **vertices / nodes**, và \(E\) là tập các **edges** nối giữa các node.

Với graph có hướng, một edge có thể được biểu diễn dưới dạng cặp có thứ tự:

$$
(u,v)\in E
$$

Với graph vô hướng, edge giữa \(u\) và \(v\) có thể hiểu là một cặp không có hướng:

$$
\{u,v\}\in E
$$

Trong project PYMK:

```text
Node  = User account
Edge  = Relationship / connection
Graph = Social network
```

### NetworkX

**NetworkX** là một thư viện Python dùng để tạo, phân tích và thao tác với graph.

Một số view quan trọng:

### Nodes view

Truy cập bằng:

```python
G.nodes
```

`G.nodes` cho phép xem và duyệt các node trong graph.

Ví dụ:

```python
list(G.nodes)
```

trả về danh sách tất cả các node.

Node view có thể được dùng để:

- duyệt node;
- lấy hoặc thêm thuộc tính node;
- kiểm tra số lượng node.

---

### Edges view

Truy cập bằng:

```python
G.edges
```

`G.edges` cho phép xem các edge trong graph.

Ví dụ:

```python
list(G.edges)
```

có thể trả về:

```text
[(u1, v1), (u2, v2), ...]
```

Edge view có thể được dùng để:

- duyệt edge;
- lấy thuộc tính edge;
- kiểm tra số lượng edge.

---

### Adjacency / Neighbors view

Truy cập bằng:

```python
G.adj
```

hoặc:

```python
G.neighbors(node)
```

Cho biết các node kết nối trực tiếp với một node.

Ví dụ:

```python
list(G.neighbors(1))
```

trả về các neighbor trực tiếp của node `1`.

`G.adj` là một object dạng dictionary-like, trong đó mỗi node ánh xạ tới các neighbor của nó và thông tin edge liên quan.

---

### Degree view

Truy cập bằng:

```python
G.degree
```

Degree cho biết số lượng edge kết nối với mỗi node.

Ví dụ:

```python
G.degree[1]
```

trả về degree của node `1`.

Trong mạng xã hội:

```text
degree ≈ số connection trực tiếp của một user
```

---

## 2. Node / Vertex

**Node** hay **vertex** là một đối tượng trong graph.

Trong project:

```text
Node = User account
```

Trong thực tế, node nên được biểu diễn bằng một định danh ổn định, ví dụ:

```text
user_id
```

NetworkX cho phép node là:

- integer;
- string;
- hoặc các giá trị hashable khác.

Node cũng có thể chứa **attributes** để lưu metadata.

### Node attributes

Ban đầu, PYMK có thể chỉ cần:

```text
node_id
```

Sau này có thể bổ sung thêm feature như:

```text
node_id
age_group
location
account_age
activity_level
```

Các feature này mô tả thêm thông tin thực tế của user, trong khi `node_id` dùng để xác định node trong graph.

---

## 3. Edge

**Edge** biểu diễn mối quan hệ giữa hai node.

Ví dụ:

$$
(A,B)\in E
$$

nghĩa là giữa `A` và `B` tồn tại một relationship theo định nghĩa của graph.

NetworkX cũng cho phép edge chứa attributes, ví dụ:

```text
weight
```

### Trong PYMK

Edge có hai vai trò quan trọng.

### 3.1. Current relationship

Ví dụ:

```text
A ───────── B
```

Nếu edge giữa `A` và `B` đã tồn tại thì hai user đã có connection.

Do đó:

> Không cần recommend `B` cho `A` nữa.

---

### 3.2. Ground truth cho Link Prediction

**Ground truth** là tập edge thực sự tồn tại trong mạng.

Để đánh giá khả năng dự đoán, ta có thể **cố tình giấu một số edge** khỏi graph dùng để huấn luyện.

Ví dụ:

```text
Graph gốc
A ───── B ───── C
```

Giấu edge `(B, C)`:

```text
Graph dùng để train
A ───── B       C
```

Model phải dự đoán liệu giữa `B` và `C` có khả năng tồn tại edge hay không.

Nếu model gán score cao cho những edge thực sự đã bị giấu thì model đang dự đoán tốt.

Về sau dữ liệu có thể được chia thành:

```text
Train edges
Validation edges
Test edges
```

---

## 4. Non-edge

Nếu:

$$
(u,v)\notin E
$$

thì cặp `(u,v)` là một **non-edge**.

Trong PYMK, câu hỏi cốt lõi là:

> Trong các non-edge, cặp nào có tiềm năng trở thành edge nhất?

Không phải mọi non-edge đều là candidate tốt.

Ví dụ, nếu Bách có khoảng một triệu user chưa kết nối thì có thể tồn tại khoảng một triệu non-edge liên quan tới Bách. Ta không muốn tính score cho toàn bộ số cặp đó.

Flow cơ bản:

```text
All non-edges
      │
      ▼
Candidate Generation
      │
      ▼
Small Candidate Set
      │
      ▼
Link Prediction / Scoring
      │
      ▼
Ranking
```

### 4.1. Non-edges

Là tập các cặp node chưa tồn tại edge.

Ví dụ:

```text
Bach ───── An
Bach       Nam
```

Nếu `Bach` chưa kết nối với `Nam` thì:

$$
(Bach,Nam)\notin E
$$

và `(Bach, Nam)` là một non-edge.

---

### 4.2. Candidate Generation

Thay vì xét toàn bộ non-edge, ta lọc ra một tập nhỏ hơn gồm những cặp có khả năng đáng quan tâm hơn dựa trên heuristic.

Ví dụ:

- chỉ lấy user có ít nhất một bạn chung với target user;
- chỉ lấy user nằm trong vùng 2-hop;
- có thể bổ sung thêm điều kiện về degree, activity hoặc các rule khác ở giai đoạn sau.

Mục tiêu của bước này là:

> Giảm mạnh số lượng cặp cần đưa vào bước scoring.

---

### 4.3. Small Candidate Set

Ví dụ:

```text
1,000,000 non-edges
        │
        ▼
Candidate Generation
        │
        ▼
5,000 candidates
```

Thay vì tính score cho một triệu cặp, ta chỉ cần xử lý vài nghìn candidate.

---

### 4.4. Link Prediction

Sau khi có candidate set, ta tính score bằng các structural feature hoặc model khác nhau.

Ví dụ:

```text
Common Neighbors
Jaccard Coefficient
Adamic-Adar
Graph Embedding
Machine Learning
GNN
```

Sau đó:

```text
Candidate Set
     │
     ▼
Calculate Score
     │
     ▼
Sort by Score
     │
     ▼
Top-k Recommendations
```

---

## 5. Directed vs. Undirected Graph

### 5.1. Undirected Graph

Trong **undirected graph**, edge không có hướng.

Nếu `u` kết nối với `v` thì quan hệ cũng tồn tại theo chiều ngược lại.

```text
u ───────── v
```

Có thể hiểu:

```text
u connected to v
=
v connected to u
```

Ví dụ điển hình:

```text
Facebook friendship
```

Trong NetworkX:

```python
G = nx.Graph()
```

Đây là cách biểu diễn phù hợp cho PYMK baseline nếu relationship là friendship hai chiều.

---

### 5.2. Directed Graph

Trong **directed graph**, edge có hướng.

```text
u ───────▶ v
```

khác với:

```text
v ───────▶ u
```

Ví dụ:

- follow trên Twitter/X;
- trust trong Bitcoin-OTC;
- transaction;
- message.

Trong NetworkX:

```python
G = nx.DiGraph()
```

Với directed graph, có thể phân biệt:

```text
in_degree
out_degree
degree
```

### Ứng dụng với PYMK

Nếu dataset biểu diễn:

```text
friendship
```

thì **undirected graph** thường hợp lý.

Nếu dataset biểu diễn:

```text
follow
trust
transaction
message
```

thì cần cân nhắc **directed graph** để giữ lại ý nghĩa của hướng.

---

## 6. Weighted vs. Unweighted Graph

### 6.1. Unweighted Graph

Trong unweighted graph, edge chỉ biểu diễn:

```text
có kết nối / không có kết nối
```

Có thể xem mọi edge có cùng trọng số:

$$
w(u,v)=1
$$

Ví dụ:

```text
Bach ───────── An
```

Ta chỉ quan tâm edge có tồn tại hay không, không quan tâm hai user đã tương tác bao nhiêu lần.

Trong NetworkX:

```python
G.add_edge("Bach", "An")
```

Với PYMK baseline, nếu chỉ cần biết hai user có friendship hay không thì **unweighted graph** là đủ.

---

### 6.2. Weighted Graph

Trong weighted graph, mỗi edge có trọng số:

$$
w(u,v)
$$

biểu diễn mức độ mạnh/yếu của relationship.

Ví dụ:

- số lần nhắn tin;
- số lần tương tác;
- message frequency;
- trust score;
- số lần cùng tham gia group/event.

Ví dụ:

```text
Bach ──(12 messages)── An
Bach ──(80 messages)── Minh
```

Hai edge đều tồn tại nhưng mức độ tương tác khác nhau.

---

## 7. Neighbor

Neighborhood của node \(u\) thường được ký hiệu:

$$
N(u)
$$

Trong undirected graph:

$$
N(u)=\{v\in V\mid \{u,v\}\in E\}
$$

Nói đơn giản:

> \(N(u)\) là tập các node kết nối trực tiếp với \(u\).

Ví dụ:

```text
          An
          │
Minh ─── Bach ─── Lan
```

Khi đó:

$$
N(Bach)=\{An,Minh,Lan\}
$$

Vì PYMK là cơ chế gợi ý **connection mới**, những user đã nằm trong \(N(u)\) phải bị loại khỏi recommendation.

Do đó:

> Candidate set phải gồm các **non-neighbor** của target user.

Sau khi có candidate mới thực hiện scoring.

---

## 8. Degree

Degree của node \(u\) trong undirected graph được ký hiệu:

$$
\deg(u)
$$

và bằng số neighbor trực tiếp của \(u\):

$$
\deg(u)=|N(u)|
$$

Ví dụ:

```text
          An
          │
Minh ─── Bach ─── Lan
          │
         Hung
```

Ta có:

$$
N(Bach)=\{An,Minh,Lan,Hung\}
$$

nên:

$$
\deg(Bach)=4
$$

Trong mạng xã hội:

> Degree có thể hiểu đơn giản là số connection trực tiếp của một user.

---

## 9. Path

Một **path** là chuỗi node liên tiếp được nối với nhau bằng edge.

Ví dụ:

```text
Bach ─── An ─── Nam ─── Linh
```

Có thể biểu diễn path:

$$
Bach\rightarrow An\rightarrow Nam\rightarrow Linh
$$

Trong unweighted graph, **path length** được tính theo số edge.

Ví dụ:

```text
Bach ─── An ─── Nam
```

có:

$$
\text{length}=2
$$

vì path đi qua hai edge:

```text
Bach ─── An
An   ─── Nam
```

### Shortest path

Trong unweighted graph, shortest path là path có ít edge nhất.

Trong weighted graph, nếu thuật toán sử dụng edge weight làm cost thì shortest path là path có tổng cost nhỏ nhất.

---

## 10. Shortest Path và PYMK

Ký hiệu khoảng cách shortest path giữa hai node \(u\) và \(v\):

$$
d(u,v)
$$

Giả sử:

```text
Bach ─── An ─── Nam
```

thì:

$$
d(Bach,Nam)=2
$$

Do đó `Nam` là **2-hop neighbor** của `Bach`.

### 1-hop neighbor

```text
Bach ─── An
```

Ta có:

$$
d(Bach,An)=1
$$

`An` là 1-hop neighbor của `Bach`.

Trong PYMK:

```text
1-hop neighbor
= connection hiện tại
= phải exclude khỏi recommendation
```

### 2-hop neighbor

```text
Bach ─── An ─── Nam
```

Ta có:

$$
d(Bach,Nam)=2
$$

Có thể hiểu trực quan:

```text
2-hop neighbor
= bạn của bạn
= candidate tiềm năng
```

---

## 11. Nhưng 2-hop là chưa đủ

Giả sử graph:

```text
          An
         /  \
      Bach  Nam
         \  /
         Minh
```

Giữa `Bach` và `Nam` có hai common neighbor:

```text
An
Minh
```

Do đó:

$$
|N(Bach)\cap N(Nam)|=2
$$

Trong khi đó:

```text
Bach ─── X ─── Lan
```

`Bach` và `Lan` chỉ có một common neighbor:

```text
X
```

nên:

$$
|N(Bach)\cap N(Lan)|=1
$$

Cả `Nam` và `Lan` đều là 2-hop candidate của `Bach`, nhưng cấu trúc liên kết của chúng không giống nhau.

Nếu dùng **Common Neighbors** làm score thì:

$$
score(Bach,Nam)>score(Bach,Lan)
$$

Điều này cho thấy:

> Chỉ biết candidate có nằm trong 2-hop hay không vẫn chưa đủ để ranking.

Ta cần thêm các **structural features**.

### Flow chuẩn của PYMK

```text
Target User
    │
    ▼
Find 2-hop Candidates
    │
    ▼
Calculate Structural Features
    │
    ▼
Link Prediction Score
    │
    ▼
Rank Candidates
    │
    ▼
Top-k Recommendations
```

### Common Neighbors

Số lượng neighbor chung của hai node:

$$
CN(u,v)=|N(u)\cap N(v)|
$$

### Jaccard Coefficient

Tỷ lệ neighbor chung trên tổng số neighbor khác nhau:

$$
J(u,v)=
\frac{|N(u)\cap N(v)|}
{|N(u)\cup N(v)|}
$$

### Adamic-Adar Index

Adamic-Adar giảm ảnh hưởng của những common neighbor có degree rất lớn:

$$
AA(u,v)=
\sum_{z\in N(u)\cap N(v)}
\frac{1}{\log \deg(z)}
$$

Trực giác:

> Một common neighbor có ít connection thường mang nhiều thông tin hơn một user kết nối với rất nhiều người.

---

## 12. Formalize Candidate Generation

Giả sử target user là \(u\).

### 12.1. 1-hop neighbors

Tập neighbor trực tiếp:

$$
N(u)
$$

Đây là những user đã có connection với \(u\).

---

### 12.2. 2-hop pool

Ta lấy neighbor của tất cả node trong \(N(u)\):

$$
N_{2}^{\text{pool}}(u)
=
\bigcup_{v\in N(u)}N(v)
$$

Lưu ý:

> \(N_{2}^{\text{pool}}(u)\) ở đây là **pool sinh từ neighbors-of-neighbors**, chưa phải candidate set cuối cùng.

Pool này có thể chứa:

- chính \(u\);
- 1-hop neighbor của \(u\);
- các node thực sự nằm ở distance 2.

---

### 12.3. Candidate set

Ta loại bỏ:

- chính target user \(u\);
- các 1-hop neighbor \(N(u)\).

Khi đó:

$$
C(u)=
\left(
\bigcup_{v\in N(u)}N(v)
\right)
\setminus
\left(
N(u)\cup\{u\}
\right)
$$

Đây là candidate set dùng cho PYMK baseline dựa trên 2-hop.

---

### Ví dụ với Bach

Giả sử:

$$
N(Bach)=\{An,Minh\}
$$

và:

$$
N(An)=\{Bach,Nam\}
$$

$$
N(Minh)=\{Bach,Nam\}
$$

Khi đó:

$$
N_{2}^{\text{pool}}(Bach)
=
N(An)\cup N(Minh)
$$

$$
=
\{Bach,Nam\}
$$

Loại bỏ chính `Bach` và các connection trực tiếp:

$$
C(Bach)
=
N_{2}^{\text{pool}}(Bach)
\setminus
\left(
N(Bach)\cup\{Bach\}
\right)
$$

suy ra:

$$
C(Bach)=\{Nam\}
$$

### Ý nghĩa

Candidate Generation biến bài toán:

```text
Xét tất cả user chưa kết nối
```

thành:

```text
Chỉ xét một tập nhỏ user có liên hệ cấu trúc với target
```

Đây là bước giúp PYMK có thể scale tốt hơn trước khi thực hiện scoring.

---

## 13. Connected Component

**Connected component** là một tập node trong undirected graph mà giữa mọi cặp node trong tập đều tồn tại một path.

Ví dụ:

```text
Component 1

A ─── B ─── C
    /
   D


Component 2

X ─── Y
```

Giữa `A` và `C` tồn tại path:

```text
A ─── B ─── C
```

nên chúng thuộc cùng connected component.

Nhưng giữa `A` và `X` không tồn tại path, nên chúng nằm ở hai component khác nhau.

### Ý nghĩa với PYMK

Nếu PYMK chỉ dựa vào structural signal như:

- 2-hop neighbor;
- Common Neighbors;
- Jaccard;
- Adamic-Adar;

thì các heuristic này không tạo ra tín hiệu giữa hai node thuộc hai connected component hoàn toàn tách biệt.

Do đó, khi làm **EDA dataset**, cần kiểm tra cấu trúc connected component.

Một số thống kê quan trọng:

```text
Number of connected components
Size of each component
Largest / giant connected component
Percentage of nodes in the giant component
```

Ví dụ:

```text
Giant component = 95% tổng số node
```

nghĩa là phần lớn user nằm trong cùng một mạng lưới liên thông.

Nếu graph có rất nhiều component nhỏ tách biệt thì các phương pháp PYMK thuần structural sẽ chủ yếu sinh recommendation bên trong từng component.

### NetworkX

Với undirected graph:

```python
nx.connected_components(G)
```

Với directed graph:

```python
nx.weakly_connected_components(G)
nx.strongly_connected_components(G)
```

---

## Tổng kết

Toàn bộ flow cơ bản của PYMK có thể biểu diễn như sau:

```text
Social Network
      │
      ▼
Graph G = (V, E)
      │
      ▼
Choose Target User u
      │
      ▼
Find Non-neighbors
      │
      ▼
Generate 2-hop Candidates
      │
      ▼
Calculate Structural Features
      │
      ▼
Compute Link Prediction Score
      │
      ▼
Rank Candidates
      │
      ▼
Top-k People You May Know
```

Các khái niệm cần nắm ở giai đoạn Graph Fundamentals:

```text
Graph G = (V, E)
Node / Vertex
Edge
Non-edge
Neighbor
Degree
Path
Shortest Path
1-hop Neighbor
2-hop Neighbor
Candidate Generation
Connected Component
Directed / Undirected Graph
Weighted / Unweighted Graph
```

Sau phần này, bước tiếp theo mới cần đi sâu vào cách tính và so sánh các **Link Prediction scores**, ví dụ:

```text
Common Neighbors
Jaccard Coefficient
Adamic-Adar Index
```

Sau đó mới tiếp tục tới các phương pháp nâng cao hơn như embedding, machine learning hoặc GNN.
