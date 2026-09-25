# Track ingestion service (STO-11)

`person_search.services.track_ingestion.TrackIngestionService.ingest_track` là consumer của
[track ingestion contract v1](track-ingestion-contract.md). Service điều phối ghi một track
xuyên PostgreSQL, MinIO và Milvus sao cho track chỉ searchable khi cả ba nơi đã hoàn chỉnh.

## Write flow

Không giữ transaction PostgreSQL trong lúc gọi MinIO/Milvus. Mỗi bước PostgreSQL là một
transaction ngắn, khóa dòng `person_tracks` bằng `SELECT ... FOR UPDATE`.

| Bước | Kho | Hành động |
| --- | --- | --- |
| 1. Register | PostgreSQL | Kiểm tra Camera/area, job, AI config và encoder; insert `PersonTrack(PENDING)` kèm object key deterministic, SHA-256 và kích thước frame; insert outbox `track.ingest` trong cùng transaction. |
| 2. Frame upload | MinIO | `put_frame` idempotent; xác nhận key và checksum trả về khớp request. |
| 3. Vector upsert | Milvus | Upsert theo primary key `track_id`, retry không nhân bản vector. |
| 4. Publish | PostgreSQL | Track vẫn `PENDING` thì set `vector_indexed_at`, chuyển `READY`; outbox `COMPLETED`. |

Lỗi validation hoặc tham chiếu ở bước 1 (`TrackReferenceError`) bị từ chối trước khi có artifact.
Lỗi hạ tầng ở bước 1 được ném lại cho producer; delivery at-least-once bảo đảm producer retry.

## Idempotency

| Trạng thái hiện có | Kết quả khi producer retry cùng `track_id` |
| --- | --- |
| Không có | Chạy toàn bộ write flow. |
| `PENDING` | Chạy lại bước 2-4; mọi bước đều idempotent. |
| `READY` | No-op, trả `READY`. |
| `FAILED` | Trả `FAILED`; đưa lại về `PENDING` thuộc STO-12. |
| Khác identity (camera, job, config, thời gian, bbox, frame SHA-256, encoder) | `TrackIngestionConflictError`, không ghi đè. |

## Retry và phân loại lỗi

- Non-retryable: `TrackIngestionError`, `FrameConflictError`, `InvalidFrameError`,
  `InvalidVectorError`, `CollectionContractError` và `ValueError` khác. Track chuyển `FAILED`,
  outbox `DEAD`.
- Retryable: lỗi còn lại (mất kết nối, timeout, dịch vụ unavailable). Outbox tăng `attempts`,
  `available_at = now + backoff` (exponential, mặc định 2s, trần 300s). Track giữ `PENDING`.
- Đạt `RetryPolicy.max_attempts` (mặc định 5): track `FAILED`, outbox `DEAD`.
- `failure_code` có dạng `<STEP>_FAILED`; `failure_message` chỉ chứa tên bước và loại exception,
  không chứa message gốc để tránh rò endpoint/credential.
- Nếu PostgreSQL chết cả lúc ghi lỗi, exception được ném ra; track vẫn `PENDING` và outbox vẫn
  đến hạn để worker STO-12 xử lý.

## Outbox payload

`storage_outbox_events.payload` (version 1) chứa `correlation_id`, `area_id`, `camera_id`,
`appeared_at_utc`, `frame_object_key`, `frame_sha256`, `encoder_version` và `embedding`
(256 float). Embedding được lưu để worker STO-12 tự retry bước Milvus. Frame bytes không được lưu;
nếu MinIO lỗi, chỉ producer gửi lại mới khôi phục bước upload.

## Gate searchable

Milvus upsert ghi `index_status="READY"` ngay, nên giữa bước 3 và 4 vector đã có trong Milvus
trong khi PostgreSQL còn `PENDING`. Đường đọc (STO-13) bắt buộc lọc hit qua
`PersonTrackRepository.ready_ids(...)`; PostgreSQL là nguồn sự thật về trạng thái searchable.

## Logging

Log chỉ gồm `correlation_id`, `track_id`, bước, loại exception và cờ retryable. Không log frame
bytes, vector hoặc message lỗi gốc.
