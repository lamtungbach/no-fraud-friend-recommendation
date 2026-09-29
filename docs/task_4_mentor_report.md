# Task 4 — Benchmark baseline PYMK và hướng dẫn sử dụng

Tài liệu này dùng để báo cáo riêng Task 4 sau phần tổng quan Sprint 1.

## 1. Task 4 đã làm gì?

Task 4 đánh giá baseline topology cho PYMK theo protocol tái lập và leakage-safe: **khi chỉ nhìn observed graph, scorer nào xếp hidden positive link cao hơn candidate khó?** Đây là **missing-link/link-reconstruction proxy**, không phải dự đoán bạn bè phát sinh trong tương lai theo timestamp.

| Thành phần | Thiết lập |
|---|---|
| Seed | 42 |
| Positive split | train/validation/test = 70% / 15% / 15% |
| Leakage control | Mask toàn bộ validation và test positive khỏi observed graph trước khi sinh candidate/score. |
| Task | `directed` và `mutual` |
| Negative mode | `random` và `hard` two-hop |
| Baseline scorer | Random, Common Neighbors, Jaccard, Adamic-Adar, Preferential Attachment |
| Quy mô sample | Tối đa 100 test positive/task; 30 ranking negatives/query |
| Tổng benchmark | 2 task × 2 negative mode × 5 scorer = **20 dòng kết quả** |

`hard` negative là candidate two-hop trông giống một gợi ý PYMK thật, nên khó hơn random negative và sát thực tế hơn.

## 2. Cách chạy Task 4

Chạy tại thư mục gốc project:

```powershell
# Chạy toàn bộ 20 cấu hình benchmark và tạo lại tất cả artifact Task 4.
.\.venv\Scripts\python.exe scripts\run_classical_experiments.py
```

Lệnh trên load MGTAB, tạo hai task, split/mask graph, sinh negative, đánh giá 5 scorer và ghi:

- `results/classical_baselines/results.csv`: 20 dòng kết quả chính.
- `results/classical_baselines/config.json`: cấu hình, seed và tổng runtime.
- `results/classical_baselines/validation_sanity.json`: sanity check pipeline trên validation; không dùng để tune scorer.
- `docs/directed_vs_mutual_experiment.md`: báo cáo so sánh sinh tự động.

```powershell
# Chỉ hiển thị các cột cần dùng khi thuyết trình Task 4.
Import-Csv results\classical_baselines\results.csv |
  Select-Object task,negative_mode,scorer,roc_auc,average_precision,recall_at_10,ndcg_at_10,hits_at_10,mrr,runtime_seconds |
  Format-Table -AutoSize

# Vẽ biểu đồ Task 4 từ results.csv; chạy benchmark phía trên trước nếu CSV chưa tồn tại hoặc đã cũ.
.\.venv\Scripts\python.exe scripts\generate_sprint1_visuals.py
```

Mở `results/sprint_1_demo/04_task4_hard_negative_benchmark.png`. Hình so sánh hard-negative benchmark theo AUC, AP và NDCG@10.

## 3. Cách giải thích performance metrics

| Metric | Ý nghĩa khi demo PYMK |
|---|---|
| ROC-AUC | Xác suất positive được score cao hơn negative; càng gần 1 càng tốt. |
| Average Precision (AP) | Chất lượng precision–recall; hữu ích khi positive hiếm/mất cân bằng. |
| Recall@K / Hits@K | Tỷ lệ hidden positive xuất hiện trong top-K. |
| MRR | Positive đúng xuất hiện sớm đến đâu; rank càng cao thì MRR càng lớn. |
| NDCG@K | Chất lượng thứ tự trong top-K, ưu tiên positive ở vị trí đầu; trực quan nhất cho danh sách gợi ý. |
| Candidate coverage | Tỷ lệ hidden positive đã nằm trong two-hop candidate pool trước khi rank. |
| Runtime | Chi phí sample benchmark; dùng so sánh tốc độ tương đối, không phải latency production. |

Không so sánh random-negative và hard-negative như hai mức khó tương đương: random thường dễ hơn. Khi nói về PYMK, ưu tiên `hard` vì negative giống candidate thật hơn.

## 4. Kết quả cần nói trong buổi báo cáo

Trên **Mutual + hard negatives** (thiết lập gần PYMK nhất):

| Scorer | ROC-AUC | AP | NDCG@10 | Diễn giải |
|---|---:|---:|---:|---|
| Common Neighbors | 0.9543 | 0.9410 | **0.8261** | Top-10 được sắp xếp tốt nhất trong các baseline. |
| Adamic-Adar | **0.9585** | 0.9459 | 0.8192 | Dẫn AUC; AP gần cao nhất. |
| Jaccard | 0.9535 | **0.9459** | 0.7405 | AP cao nhưng thứ tự top-10 kém hơn hai scorer trên. |
| Preferential Attachment | 0.8254 | 0.7797 | 0.4956 | Yếu hơn rõ rệt. |
| Random | 0.5306 | 0.5336 | 0.1529 | Mốc tham chiếu gần ngẫu nhiên. |

Kết luận: Mutual + hard negative là application proxy phù hợp để demo PYMK; Common Neighbors dẫn NDCG@10, còn Adamic-Adar dẫn ROC-AUC. Vì metric ưu tiên mục tiêu khác nhau, chưa nên tuyên bố một scorer “thắng tuyệt đối”.

- Mutual có `candidate_coverage = 1.00`: mọi hidden positive trong sample đều nằm trong two-hop pool; benchmark đang đánh giá năng lực ranker trên pool.
- Directed khó hơn: hard-negative Common Neighbors có AUC 0.6837 và NDCG@10 0.3779, coverage 0.88. Vì vậy Directed là benchmark phụ, còn Mutual phù hợp hơn làm application proxy.

## 5. Script nói ngắn (khoảng 1 phút)

“Ở Task 4, em đánh giá các baseline topology trong điều kiện leakage-safe: toàn bộ link validation và test được mask khỏi graph trước khi sinh candidate và tính score. Em chạy 20 cấu hình từ hai semantics, hai loại negative và năm scorer. Random negative dễ hơn, nên em tập trung vào hard two-hop negatives. Với Mutual + hard, Adamic-Adar dẫn AUC 0.9585, còn Common Neighbors có NDCG@10 cao nhất 0.8261. Candidate coverage bằng 1.00 cho thấy hidden positive đã nằm trong pool trước khi rank. Vì các metric tối ưu mục tiêu khác nhau, em chọn Mutual làm application proxy hiện tại nhưng chưa kết luận một scorer thắng tuyệt đối.”

## 6. Câu hỏi thường gặp

- **Có leakage không?** Không: validation/test positive bị mask trước candidate generation và scoring.
- **Có dùng validation để chọn model không?** Chưa. `validation_sanity.json` chỉ kiểm tra pipeline, không dùng thay đổi scorer trước test.
- **Vì sao sample 100 positive?** Để chạy local nhanh, tái lập được trong Sprint 1; chưa phải benchmark production-scale.
- **Task 4 có xử lý fraud không?** Chưa. Fraud filtering thuộc Trust/Fraud Agent ở sprint sau.
