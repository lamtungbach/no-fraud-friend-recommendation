# GIAI ĐOẠN 08 — Batch pipeline + metadata PostgreSQL + sự kiện vòng đời

> Chỉ triển khai giai đoạn này. `AGENTS.md` là tài liệu có thẩm quyền. Không tự động bắt đầu GIAI ĐOẠN 09.

## 1. Mục tiêu

Triển khai vòng đời offline biến dataset snapshot thành graph/index version đã active và báo serving biết version mới sẵn sàng.

```text
dataset/job request -> DatasetAdapter -> CanonicalGraph -> validation -> GraphView -> ServingGraphIndex -> immutable artifact -> job/version metadata -> activate -> graph-index-ready
```

GIAI ĐOẠN 07 phải PASS; versioned artifact và online service đã ổn định.

## 2. Sở hữu và phạm vi

Bách làm lifecycle PYMK graph/index, không làm pipeline training Trust/Fraud của Linh; chỉ biểu diễn lifecycle Trust bằng interface/event khi cần. Phạm vi: batch orchestrator, chọn DatasetAdapter, validation, graph/index build, artifact persistence, pipeline job, PostgreSQL metadata, active-version metadata, lifecycle event abstraction, Redpanda nếu môi trường dùng, producer/consumer idempotent, reload trigger và test.

## 3. Job, API và PostgreSQL

State gợi ý: `PENDING, RUNNING, VALIDATING, PERSISTING, READY, FAILED`; giữ state machine tốt hơn nếu repo có. Operations: `create_dataset_or_index_job(...)`, `get_job(job_id)`; HTTP sau này có thể là `POST /datasets/jobs`, `GET /datasets/jobs/{job_id}`.

PostgreSQL chỉ lưu metadata, không lưu adjacency để duyệt request-time. Entity gợi ý: `datasets`, `pipeline_jobs`, `graph_versions`, `active_versions`. Metadata gồm dataset/source, job status/error, version, node/edge count, semantics, artifact location/checksum, thời điểm tạo/active, tóm tắt config build/benchmark.

## 4. Kích hoạt và event

Thứ tự bắt buộc: build N → validate N → persist immutable N → persist metadata N → đánh dấu ACTIVE nguyên tử → publish `graph-index-ready(N)`. Nếu publish lỗi sau DB activation, thiết kế retry/idempotency. Event abstraction độc lập Redpanda; payload tối thiểu `event_id`, `event_type`, `version`, `created_at`, artifact/checksum metadata; consumer idempotent.

Khi nhận ready(N): tải N → validate → warm/smoke test → đổi in-memory active index. Version xấu không được phá version khỏe cũ. Raw/uploaded data phải ngoài Git, đi qua storage abstraction, không log private/raw data; parser riêng dataset nằm trong adapter.

## 5. Kiểm thử và tiêu chí

Test success lifecycle, adapter/validation/artifact failure, DB consistency, failed activation giữ version cũ, event retry/duplicate idempotent, correct service load, corrupt artifact bị từ chối, READY không trước validation.

- [ ] Có boundary DatasetAdapter → CanonicalGraph; version bất biến/validate trước active.
- [ ] Postgres chỉ metadata; job transition được test; ordering an toàn.
- [ ] Event versioning/duplicate idempotent; version xấu giữ serving cũ.
- [ ] Không làm Trust model internals.

Bàn giao orchestrator, job/version model, persistence/migration nếu cần, event abstraction/Redpanda adapter, test và báo cáo. DỪNG; không tạo Kubernetes deployment.
