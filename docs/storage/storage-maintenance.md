# Retry và reconciliation (STO-12)

Code: `person_search.services.storage_maintenance` và CLI `person-search-storage`
(`person_search.storage.maintenance_cli`).

## Outbox retry worker

`OutboxRetryWorker.run_once(limit)`:

1. Transaction ngắn claim event `track.ingest` đến hạn bằng `FOR UPDATE SKIP LOCKED`:
   `PENDING` có `available_at <= now`, hoặc `PROCESSING` có `locked_at` quá `lock_timeout`
   (mặc định 5 phút, tức worker trước đó chết giữa chừng). Event chuyển `PROCESSING`.
2. Gọi `TrackIngestionService.resume(track_id)` cho từng track:
   - `READY`: đánh dấu event `COMPLETED`.
   - `FAILED`: đánh dấu event `DEAD`.
   - `PENDING`: `head_frame` kiểm tra object và checksum trên MinIO, upsert vector từ
     embedding trong payload outbox, rồi publish `READY`.
3. Lỗi đi qua cùng chính sách của STO-11: retryable thì backoff, hết `max_attempts` thì
   `FAILED`/`DEAD`. Frame thiếu trên MinIO là retryable (producer có thể gửi lại) nhưng
   worker không tự upload được vì outbox không chứa frame bytes.
4. Exception không bắt được (ví dụ PostgreSQL chết) được đếm vào `errors`; event giữ
   `PROCESSING` và được claim lại sau `lock_timeout`.

`requeue_failed(track_id)` là retry tường minh: `FAILED → PENDING`, event về `PENDING`,
`attempts = 0`, ghi audit `storage.track_requeued`.

## Reconciliation

`StorageReconciler.run(delete_orphans=False)` mặc định là dry-run và chỉ báo cáo:

| Nhóm | Cách phát hiện |
| --- | --- |
| `stale_tracks` | Track `PENDING/FAILED` có `updated_at` cũ hơn `stale_after` (mặc định 30 phút). |
| `missing_objects` | Track `READY` mà `head_frame` báo không có object. |
| `checksum_mismatches` | Track `READY` có checksum trên MinIO khác `frame_sha256`. |
| `missing_vectors` | Track `READY` không có vector trong Milvus. |
| `orphan_objects` | Object dưới `frame_prefix` không map được tới track PostgreSQL. |
| `orphan_vectors` | Vector trong collection không có track PostgreSQL. |

Quét theo batch (`batch_size`, mặc định 200) và dừng ở `max_items` (mặc định 10.000); khi dừng
sớm thì `truncated = true`.

`delete_orphans=True` chỉ xóa object/vector orphan, kiểm tra lại PostgreSQL ngay trước khi xóa,
bỏ qua mọi track ID còn được `CaseResult` tham chiếu, và ghi audit `storage.orphans_deleted`
kèm số lượng. Track `READY` thiếu object/vector không bị hạ trạng thái vì `READY` không được
chuyển ngược; báo cáo dùng để xử lý thủ công (restore object hoặc re-index).

## CLI

```
person-search-storage retry-outbox --limit 50
person-search-storage reconcile                      # dry-run, exit 2 nếu có sai lệch
person-search-storage reconcile --delete-orphans --actor-user-id <uuid>
person-search-storage requeue-track <track_id> --actor-user-id <uuid>
```
