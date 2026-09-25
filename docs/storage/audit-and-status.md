# Audit log và trạng thái vận hành lưu trữ (STO-16)

## Audit

Code: `person_search.services.audit`.

- `AuditEvent` là catalog event duy nhất được chấp nhận: auth, user, area Operator, camera,
  AI state/config, Case mutation, `storage.track_failed`, `storage.track_requeued`,
  `storage.orphans_deleted` và `system.technical_failure`. Không có event cho lượt tìm kiếm.
- `record_audit(repositories, ...)` ghi trong cùng transaction với mutation.
  `AuditRecorder.record_standalone(...)` ghi trong transaction riêng cho sự kiện thất bại (mutation
  đã rollback) và không ném lỗi nếu chính audit ghi thất bại, chỉ log.
- Actor snapshot (`username`, `role`) được lưu trong metadata vì `actor_user_id` bị `SET NULL`
  khi user bị xóa cứng.
- `redact_metadata` áp dụng cho mọi metadata:
  - key kết thúc bằng `password`, `password_hash`, `secret`, `token`, `api_key`, `access_key`,
    `private_key`, `credential(s)`, `authorization`, `cookie`, `session_id`, `embedding`,
    `vector`, `frame_bytes`, `image_bytes`, `raw_image`, `rtsp_url` bị thay bằng `[REDACTED]`;
  - credential trong URL (`scheme://user:pass@host`) bị che;
  - bytes và dãy số dài hơn 16 phần tử (vector) bị che;
  - ký tự điều khiển bị thay bằng khoảng trắng (chống log injection), chuỗi cắt ở 500 ký tự,
    tối đa 50 phần tử mỗi collection, sâu tối đa 5 cấp.
- `AuditLogService.list` chỉ cho Admin `ACTIVE`; lọc theo khoảng thời gian, actor, event type,
  result; sắp xếp `occurred_at DESC, id DESC` với cursor keyset; tối đa 100/trang.

Event đang được phát: `case.*` (STO-15), `storage.track_failed` khi ingestion chuyển track
`FAILED`, `storage.track_requeued`, `storage.orphans_deleted`. Các event auth/user/camera/AI được
phát khi các task BE tương ứng hiện thực nghiệp vụ đó.

## Trạng thái vận hành

Code: `person_search.services.storage_status`.

- `StorageMetrics` (in-memory theo tiến trình, thread-safe) đếm lỗi hạ tầng theo component
  `postgres`, `minio`, `milvus` kèm loại lỗi và thời điểm gần nhất, và thời gian xử lý ingestion
  (số lần, ready/pending/failed, trung bình, max).
  - Ingestion: lỗi retryable ở bước upload/verify frame tính cho MinIO, upsert/verify vector cho
    Milvus, publish và lỗi đăng ký track cho PostgreSQL. Lỗi validation không tính.
  - Search: lỗi Milvus (trừ embedding sai). Imagery: lỗi MinIO (trừ ảnh thiếu/hỏng).
- `StorageStatusService.snapshot(admin_id)` trả số track theo status, số outbox event theo status,
  tuổi của event đến hạn cũ nhất, lỗi theo component, kết quả health check (nếu truyền
  `StorageHealthService`) và danh sách cảnh báo (`dead_outbox_events`, `failed_tracks`,
  `<component>_unhealthy`).

Metric in-memory reset khi tiến trình khởi động lại và không gộp giữa API và worker; số liệu bền
vững lấy từ PostgreSQL (track/outbox) và audit log.
