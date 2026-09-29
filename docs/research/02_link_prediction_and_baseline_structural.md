# link_prediction_notes

# 02. Link Prediction

## Tổng quan

**Link Prediction** là bài toán dự đoán khả năng xuất hiện một liên kết mới giữa hai node trong graph.

Trong bài toán **People You May Know (PYMK)**:

```
Node = User
Edge = Existing relationship / friendship
Non-edge = Hai user hiện chưa kết nối
```

Mục tiêu của Link Prediction là:

> Với một cặp user hiện chưa có edge, dự đoán xem cặp đó có khả năng hình thành edge trong tương lai hay không.
> 

Có thể hiểu đơn giản:

```
Current Graph
    │
    ▼
Find Non-edges 
    │
    ▼
Estimate Link Likelihood
    │
    ▼
Score Candidates
    │
    ▼
Rank Recommendations
```

---

- Current Graph : gồm các nodes và edges
- Fine Non-edges : Tìm các cặp nút chưa có cạnh nối trực tiếp( candidate)
- Estimate Link Likelihood : Sử dụng các thuật toán hoặc chỉ số (ví dụ: Common Neighbors, Jaccard, Adamic-Adar, hoặc mô hình học máy) để **ước lượng xác suất** rằng một non-edge sẽ trở thành cạnh thật.
- Score Candidates: Gán **điểm số** cho từng cặp ứng viên dựa trên xác suất hoặc độ mạnh của khả năng hình thành liên kết.
- Rank Recommendations :Sắp xếp các ứng viên theo điểm số từ cao xuống thấp → tạo ra danh sách gợi ý liên kết (ví dụ: “gợi ý kết bạn” trên Facebook).

## 1. Link Prediction là gì?

Giả sử ta có graph:

$$
G=(V,E)
$$

Trong đó:

- (V): tập các node;
- (E): tập các edge hiện đang tồn tại.

Với hai node:

$$
u,v\in V
$$

hiện chưa có edge:

$$
(u,v)\notin E
$$

ta muốn ước lượng một giá trị:

$$
score(u,v)
$$

Giá trị này biểu diễn mức độ **có khả năng xuất hiện edge giữa (u) và (v)**.

Nếu:

$$
score(u,v)
$$

càng cao thì cặp ((u,v)) càng nên được ưu tiên trong danh sách recommendation ( rank recommendation)

Trong PYMK:

```
score cao
   ↓
khả năng hai user có quan hệ tiềm năng cao hơn
   ↓
candidate nên được xếp hạng cao hơn(rank)
```

---

## 2. Input của Link Prediction là gì?

Input cơ bản của Link Prediction gồm:

### 2.1. Graph hiện tại

$$
G=(V,E)
$$

Graph chứa:

- các node hiện có;
- các edge hiện có;
- cấu trúc kết nối giữa các node.

Ví dụ:

```
A ─── B ─── C
│
D
```

Ta biết:

```
(A, B) ∈ E
(B, C) ∈ E
(A, D) ∈ E
```

Nhưng:

```
(A, C) ∉ E
```

Do đó `(A, C)` là một non-edge có thể được đưa vào quá trình dự đoán.

---

### 2.2. Một cặp node candidate

- Candidate : là những cặp nút trong đồ thị chưa có cạnh nối trực tiếp( non-edges) nhưng có khả năng sẽ được kết nối trong tương lai.
- Node candidate = Đánh dấu và lưu lại các cặp nút chưa kết nối nhưng sẽ được xem xét trong qua trình dự đoán liên kết

Ta xét cặp:

$$
(u,v)
$$

thỏa mãn:

$$
u,v\in V
$$

và:

$$
(u,v)\notin E
$$

Cặp này là một **candidate link**.

Ví dụ:

```
Bach ─── An ─── Nam
```

Hiện tại:

```
(Bach, An) ∈ E
(An, Nam) ∈ E
(Bach, Nam) ∉ E
```

Ta có thể hỏi:

> Edge `(Bach, Nam)` có khả năng xuất hiện hay không?
> 

---

### 2.3. Feature của cặp node

Tùy phương pháp, model có thể sử dụng các feature khác nhau.

Ở baseline structural Link Prediction:

```
Common Neighbors
Jaccard Coefficient
Adamic-Adar
Preferential Attachment
Shortest Path
```

- Đều là các thước đo độ tương đồng hoặc khả năng hình thành liên kết trong mạng lưới graph, thường dùng trong link prediction hoặc phân tích mạng xã hội:
1. **Common Neighbors**
    - Ý tưởng: Hai nút càng có nhiều hàng xóm chung thì càng có khả năng kết nối với nhau.
    - Công thức:
        
        $$
        CN(u,v)=∣N(u)∩N(v)∣
        $$
        
    
    Trong đó N(u) là tập hàng xóm của nút u.
    
2. **Jaccard Coefficient**
- **Chuẩn hóa số lượng hàng xóm chung**: thay vì chỉ đếm (như Common Neighbors), Jaccard tính tỷ lệ, giúp công bằng hơn khi so sánh các nút có độ lớn khác nhau.
- **Score nằm trong khoảng [0,1]**:
    - 0 → không có hàng xóm chung
    - 1 → tất cả hàng xóm đều chung
- Ý tưởng: Đo tỷ lệ hàng xóm chung so với tổng số hàng xóm.
- Công thức:
    
    $$
    J(u,v) = \frac{|N(u) \cap N(v)|}{|N(u) \cup N(v)|}
    $$
    
- Ưu điểm: Chuẩn hóa số lượng hàng xóm chung, tránh thiên lệch khi một nút có quá nhiều hàng xóm.
- Nếu A có 100 bạn, B có 5 bạn, và họ có 3 bạn chung → Jaccard sẽ phản ánh mức độ tương đồng thấp hơn so với Common Neighbors.
    - **Common Neighbors** chỉ đơn giản đếm số bạn chung.
    → Trong ví dụ: A có 100 bạn, B có 5 bạn, họ có 3 bạn chung → score = 3.
    Nó không quan tâm đến tổng số bạn của A và B, chỉ nhìn vào con số tuyệt đối.
    - **Jaccard Coefficient** lại chuẩn hóa bằng cách chia cho tổng số bạn duy nhất của cả hai.
    → Tổng số bạn của A và B là: 100 + 5 − 3 = 102 (trừ đi phần trùng lặp).
    → Jaccard = 3/102≈0.029.
1. **Adamic–Adar Index**
- Ý tưởng: Không chỉ đếm hàng xóm chung, mà còn **giảm trọng số của hàng xóm có nhiều kết nối** (vì họ ít mang tính đặc trưng).
- Công thức:

$$
AA(u,v) = \sum_{w \in N(u) \cap N(v)} \frac{1}{\log(|N(w)|)}
$$

- Nghĩa: Nếu một hàng xóm chung có ít bạn bè, thì đóng góp của họ lớn hơn.
- Ví dụ: Nếu A và B cùng quen một người rất “hiếm” (ít kết nối), thì khả năng A–B quen nhau cao.
1. **Preferential Attachment**
- Ý tưởng: Các nút có nhiều kết nối thường dễ tạo thêm kết nối mới (nguyên lý “rich-get-richer”).
- Công thức:

$$
PA(u,v)=∣N(u)∣⋅∣N(v)∣
$$

- Nghĩa: Xác suất kết nối giữa hai nút tỷ lệ thuận với bậc (degree) của chúng.
- Ví dụ: Người nổi tiếng (nhiều bạn) dễ quen thêm người nổi tiếng khác.

Ở phương pháp nâng cao hơn có thể sử dụng:

```
Node Embeddings
Graph Embeddings
Node Attributes
Interaction Features
Machine Learning
Graph Neural Networks
```

Trong giai đoạn đầu của PYMK, ta chỉ cần tập trung vào **structural features**.

---

## 3. Output của Link Prediction là gì?

Output thường là một **score** hoặc **probability-like value** cho một cặp node.

Có thể viết:

$$
f(u,v)=score(u,v)
$$

hoặc:

$$
P((u,v)\in E_{future})
$$

nếu model được thiết kế để trả về xác suất.

Ví dụ:

```
Candidate        Score
----------------------
(Bach, Nam)      0.91
(Bach, Lan)      0.72
(Bach, Minh)     0.35
```

Ta có thể ranking:

```
1. Nam
2. Lan
3. Minh
```

Sau đó lấy:

```
Top-k candidates
```

để đưa vào recommendation.

### Flow

```
Candidate Pair
     │
     ▼
Link Prediction Model
     │
     ▼
score(u, v)
     │
     ▼
Ranking
```

---

## 4. Positive Edge là gì?

Trong Link Prediction, **positive edge** là một cặp node được xem là **có edge thật** trong ground truth.

Ví dụ:

```
A ─── B
```

thì:

$$
(A,B)\in E
$$

Do đó:

```
(A, B) = Positive Example
```

Trong dataset cho supervised Link Prediction, ta thường gán:

$$
y_{uv}=1
$$

cho positive edge.

Ví dụ:

```
(u, v)        Label
-------------------
(A, B)          1
(B, C)          1
(D, E)          1
```

### Tại sao cần positive edge?

Model cần học được:

> Những cặp node thực sự có relationship thường có cấu trúc hoặc feature như thế nào?
> 

Ví dụ:

- nhiều common neighbors;
- cùng community;
- embedding gần nhau;
- có interaction tương đồng.

---

## 5. Non-edge / Negative Edge là gì?

Nếu:

$$
(u,v)\notin E
$$

thì `(u,v)` là một **non-edge**.

Trong supervised Link Prediction, một số non-edge được chọn làm **negative examples**.

Ta có thể gán:

$$
y_{uv}=0
$$

Ví dụ:

```
(u, v)        Label
-------------------
(A, D)          0
(B, E)          0
(C, F)          0
```

### Phân biệt Non-edge và Negative Edge

Hai khái niệm này liên quan nhưng không hoàn toàn giống nhau.

**Non-edge**:

> Bất kỳ cặp node nào hiện tại chưa có edge.
> 

**Negative edge / negative sample**:

> Một non-edge được chọn làm mẫu negative trong quá trình train hoặc evaluation.
> 

Do graph có thể chứa rất nhiều non-edge nên ta thường không sử dụng toàn bộ.

Thay vào đó:

```
All Non-edges
      │
      ▼
Negative Sampling
      │
      ▼
Negative Examples
```

---

## 6. Một điểm rất quan trọng: Non-edge không chắc chắn là negative thật

Trong mạng xã hội, nếu hai user hiện chưa kết nối:

$$
(u,v)\notin E
$$

không có nghĩa là họ **không bao giờ** kết nối.

Có thể:

```
hiện tại chưa là bạn
```

nhưng:

```
tuần sau trở thành bạn
```

Do đó, trong Link Prediction:

> Non-edge thường chỉ có nghĩa là **chưa quan sát thấy edge ở thời điểm hiện tại**.
> 

Đây là lý do Link Prediction khác với classification thông thường.

Ví dụ:

```
Time t

Bach ─── An ─── Nam
```

Tại thời điểm (t):

$$
(Bach,Nam)\notin E_t
$$

Nhưng tại thời điểm (t+1):

```
Bach ─── Nam
```

có thể xuất hiện:

$$
(Bach,Nam)\in E_{t+1}
$$

Đây chính là một link mà hệ thống muốn dự đoán.

---

## 7. Formalize Link Prediction

Giả sử graph tại thời điểm hiện tại là:

$$
G_t=(V,E_t)
$$

Ta xét một cặp node:

$$
u,v\in V
$$

và:

$$
(u,v)\notin E_t
$$

Link Prediction muốn học một hàm:

$$
f:V\times V\rightarrow \mathbb{R}
$$

sao cho:

$$
f(u,v)=score(u,v)
$$

Score càng cao thì model càng đánh giá cặp này có khả năng xuất hiện edge trong tương lai.

Có thể hiểu:

$$
score(u,v)\uparrow
$$

thì:

$$
P((u,v)\in E_{t+1})\uparrow
$$

theo nghĩa trực giác.

Lưu ý:

> Không phải mọi scoring method đều trả về một probability chuẩn hóa.
> 

Ví dụ:

- Common Neighbors trả về số nguyên;
- Adamic-Adar trả về một real-valued score;
- model classification có thể trả về probability.

---

## 8. Link Prediction trong PYMK

Với PYMK, ta không cần dự đoán toàn bộ graph cùng lúc.

Ta thường chọn một target user:

$$
u
$$

Sau đó:

```
Target User u
     │
     ▼
Find Non-neighbors
     │
     ▼
Candidate Generation
     │
     ▼
Candidate Set C(u)
     │
     ▼
Compute score(u, v)
     │
     ▼
Rank Candidates
     │
     ▼
Top-k Recommendations
```

Với mỗi candidate:

$$
v\in C(u)
$$

ta tính:

$$
score(u,v)
$$

Sau đó ranking:

$$
v_1,v_2,\ldots,v_k
$$

sao cho:

$$
score(u,v_1)
\ge
score(u,v_2)
\ge
\cdots
\ge
score(u,v_k)
$$

Top candidates sẽ được đưa vào danh sách **People You May Know**.

---

## 9. Ví dụ đơn giản

Giả sử graph:

```
          An
         /  \
      Bach  Nam
         \
         Minh ─── Lan
```

Ta muốn recommendation cho:

```
Bach
```

### Current neighbors

$$
N(Bach)=\{An,Minh\}
$$

Do đó:

```
An
Minh
```

đã là connection và phải exclude.

### Candidate

`Nam` là bạn của `An`:

```
Bach ─── An ─── Nam
```

nên `Nam` là 2-hop candidate.

`Lan` là bạn của `Minh`:

```
Bach ─── Minh ─── Lan
```

nên `Lan` cũng là 2-hop candidate.

Ta có:

$$
C(Bach)=\{Nam,Lan\}
$$

Link Prediction sẽ tính:

$$
score(Bach,Nam)
$$

và:

$$
score(Bach,Lan)
$$

Giả sử:

```
score(Bach, Nam) = 2.0
score(Bach, Lan) = 1.0
```

thì ranking:

```
1. Nam
2. Lan
```

---

## 10. Training Link Prediction bằng cách giấu edge

Một cách phổ biến để đánh giá Link Prediction là:

> Lấy graph đã biết, giấu một phần edge rồi xem model có tìm lại được chúng không.
> 

Giả sử graph gốc:

```
A ─── B ─── C
│     │
D ─── E
```

Ta giấu edge:

```
(B, E)
```

Graph dùng để train / predict trở thành:

```
A ─── B ─── C
│
D ─── E
```

Model không còn nhìn thấy:

$$
(B,E)
$$

Sau đó ta đưa `(B,E)` vào candidate set.

Nếu model cho:

$$
score(B,E)
$$

cao thì model đã dự đoán đúng một hidden positive edge.

Flow:

```
Original Graph
      │
      ▼
Hide Some Positive Edges
      │
      ▼
Training Graph
      │
      ▼
Generate Candidates
      │
      ▼
Predict Scores
      │
      ▼
Check Hidden Edges
```

---

## 11. Positive và Negative khi train

Một dataset đơn giản có thể có dạng:

| Node u | Node v | Label |
| --- | --- | --- |
| A | B | 1 |
| B | C | 1 |
| D | E | 1 |
| A | C | 0 |
| B | D | 0 |
| C | E | 0 |

Trong đó:

```
Label = 1
```

nghĩa là positive edge.(“đây là kết nối thật” , những cạnh thực sự trong đồ thị) 

```
Label = 0
```

nghĩa là negative sample.(cặp node không có cạnh, được dùng làm đối chứng.)

Ta có thể viết:

$$
y_{uv}
=
\begin{cases}
1, & \text{nếu } (u,v) \text{ là positive edge}\\
0, & \text{nếu } (u,v) \text{ là negative sample}
\end{cases}
$$

Model học:

$$
(u,v,\text{features})
\rightarrow y_{uv}
$$

---

## 12. Link Prediction có hai cách nhìn chính

### 12.1. Binary Classification

Với mỗi cặp node:

```
(u, v)
```

dự đoán:

```
Edge
or
No Edge
```

Tức là:

$$
y_{uv}\in\{0,1\}
$$

Cách nhìn này hữu ích khi train Machine Learning model.

---

### 12.2. Ranking

Trong PYMK, ranking thường quan trọng hơn việc chỉ trả lời:

```
edge / no edge
```

Ta muốn biết:

> Trong hàng nghìn candidate, ai nên được recommend trước?
> 

Do đó output thực tế thường là:

```
Candidate      Score
--------------------
Nam            0.91
Lan            0.83
Hung           0.61
Hoa            0.32
```

Sau đó chọn:

```
Top-10
Top-20
Top-k
```

Vì vậy, với PYMK:

> Link Prediction nên được hiểu vừa là **dự đoán liên kết**, vừa là **ranking candidate links**.
> 

---

## 13. Relationship giữa Candidate Generation và Link Prediction

Hai bước này không giống nhau.

### Candidate Generation

Trả lời:

> Ta nên xét những node nào?
> 

Ví dụ:

```
2-hop neighbors
```

Output:

$$
C(u)
$$

---

### Link Prediction

Trả lời:

> Trong các candidate này, candidate nào tốt hơn?
> 

Input:

$$
v\in C(u)
$$

Output:

$$
score(u,v)
$$

Sau đó ranking.

## Flow hoàn chỉnh:

```
Graph
  │
  ▼
Candidate Generation
  │
  ▼
C(u)
  │
  ▼
Link Prediction
  │
  ▼
score(u, v)
  │
  ▼
Ranking
  │
  ▼
Top-k
```

Đây là điểm rất quan trọng:

> **Candidate Generation giảm search space. Link Prediction phân biệt và ranking các candidate trong search space đó.**
> 

---

## 14. Trả lời 5 câu quan trọng

### 1. Link Prediction là gì?

Link Prediction là bài toán dự đoán khả năng xuất hiện một edge giữa hai node hiện chưa có edge.

---

### 2. Input của Link Prediction là gì?

Input cơ bản gồm:

```
Graph G = (V, E)
+
Candidate node pair (u, v)
+
Features của cặp node
```

với:

$$
(u,v)\notin E
$$

---

### 3. Output là gì?

Output thường là:

$$
score(u,v)
$$

hoặc probability-like value cho khả năng xuất hiện edge.

Score càng cao thì candidate càng nên được ranking cao.

---

### 4. Positive edge là gì?

Positive edge là cặp node có edge thật trong ground truth:

$$
(u,v)\in E
$$

thường được gán:

$$
y=1
$$

---

### 5. Non-edge / negative edge là gì?

Non-edge là cặp node hiện chưa có edge:

$$
(u,v)\notin E
$$

Negative edge / negative sample là một non-edge được chọn làm mẫu negative trong train hoặc evaluation:

$$
y=0
$$

Non-edge không nhất thiết là negative thật vĩnh viễn, vì edge có thể xuất hiện trong tương lai.

---

## 15. Công thức cần nhớ

Graph:

$$
G=(V,E)
$$

Hai node:

$$
u,v\in V
$$

Candidate chưa có edge:

$$
(u,v)\notin E
$$

Link Prediction:

$$
score(u,v)
$$

Interpretation:

$$
score(u,v)\uparrow
\Rightarrow
\text{candidate được ưu tiên cao hơn}
$$

Positive edge:

$$
(u,v)\in E
$$

Negative / non-edge candidate:

$$
(u,v)\notin E
$$

Candidate set cho target user:

$$
v\in C(u)
$$

Ranking:

$$
score(u,v_1)
\ge
score(u,v_2)
\ge
\cdots
\ge
score(u,v_k)
$$

---

## 16. Full flow của Link Prediction trong PYMK

```
Social Network
      │
      ▼
Graph G = (V, E)
      │
      ▼
Target User u
      │
      ▼
Exclude Existing Neighbors
      │
      ▼
Candidate Generation
      │
      ▼
Candidate Set C(u)
      │
      ▼
Extract Structural Features
      │
      ▼
Link Prediction
      │
      ▼
score(u, v)
      │
      ▼
Rank Candidates
      │
      ▼
Top-k Recommendations
```

---