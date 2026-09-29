# Canonical schema

`CanonicalGraph` là hợp đồng dữ liệu chuẩn hóa giữa dataset adapter và các
thành phần pipeline phía sau. Engine chỉ làm việc với node IDs liên tiếp
`0..N-1`, COO `edge_index`, relation IDs canonical, feature matrix tùy chọn và
một dictionary labels tổng quát.

## Vì sao không để engine phụ thuộc MGTAB?

MGTAB chỉ là dataset đầu tiên. Dataset-specific logic nằm trong
`src/data/adapters/`; một dataset mới chỉ cần viết adapter chuyển dữ liệu về
`CanonicalGraph`, không cần sửa candidate generation, baseline, split hay
evaluation. Adapter không chứa logic PYMK, negative sampling, fraud hoặc risk.

## Fields

| Field | Bắt buộc | Contract |
|---|---:|---|
| `node_ids` | Có | Tensor shape `[N]`, canonical contiguous IDs |
| `node_features` | Không | Tensor shape `[N, F]` hoặc `None` |
| `edge_index` | Có | COO tensor shape `[2, E]`, source/destination |
| `edge_type` | Có | Tensor shape `[E]`, relation ID canonical |
| `edge_weight` | Không | Tensor shape `[E]` hoặc `None` |
| `labels` | Không | `dict[str, Tensor]`; label node-level có chiều đầu `[N]` |
| `relation_schema` | Có | ID → semantic metadata (`name`, `directed`, `description`) |
| `metadata` | Có | Dataset/schema metadata, không chứa task state |

Validator kiểm tra shape, range node ID, độ dài edge fields, feature/label
dimensions, finite values và relation IDs. Self-loop/duplicate edge được
report bằng warning nhưng không bị xóa.

## MGTAB relation mapping

Mapping được xác định từ tài liệu EDA hiện có trong repo và khai báo một lần
trong `MGTAB_RELATION_SCHEMA`: `0 followers`, `1 friends`, `2 mention`,
`3 reply`, `4 quoted`, `5 url`, `6 hashtag`. Các relation này được giữ directed
theo semantics raw; adapter không tạo undirected projection.

## Thêm dataset mới

Implement `DatasetAdapter`, nhận path/config qua constructor, đọc raw ở
`load_raw`, chuyển đổi trong `transform`, tạo `CanonicalGraph`, rồi gọi
`self.validate(graph)`. Không sửa raw files và không đưa split, candidate,
ranking hoặc fraud logic vào adapter.

```text
MGTABAdapter ───────────┐
FutureAdapter ──────────┼──> CanonicalGraph ──> PYMK
MockAdapter ────────────┘
```
