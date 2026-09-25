# PostgreSQL processing schema (STO-05)

Migration `20260925_0002` bổ sung bốn bảng:

- `ai_config_versions`: phiên bản detector, tracker, encoder và checksum checkpoint.
- `processing_jobs`: nguồn FILE/RTSP, camera, cấu hình AI, tiến độ và thời gian xử lý.
- `person_tracks`: timeline nguồn, bbox, frame trong MinIO và trạng thái vector index.
- `storage_outbox_events`: hàng đợi giao dịch để retry thao tác với kho ngoài PostgreSQL.

## Vòng đời PersonTrack

Track luôn được tạo ở `PENDING`. Các chuyển trạng thái hợp lệ là:

```text
PENDING -> READY
PENDING -> FAILED
FAILED  -> PENDING
```

`READY` là trạng thái cuối. PostgreSQL chỉ chấp nhận `READY` khi đã có object key,
SHA-256, kích thước frame dương và thời điểm vector được index. Cả trigger PostgreSQL
và guard SQLAlchemy đều bảo vệ state machine; constraint bảo vệ dữ liệu artifact.

## Truy xuất nguồn gốc

Từ `person_tracks.id` có thể lần theo `camera_id` đến Area, `processing_job_id` đến
nguồn xử lý, và `ai_config_version_id` đến model/checkpoint. Track lưu bbox, kích thước
full frame, MinIO object key và encoder version. Schema không lưu Matching Score.

## Kiểm thử nhanh

Unit test không cần dịch vụ ngoài:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_processing_models.py
```

Migration integration test yêu cầu DSN trỏ tới database dùng một lần:

```powershell
$env:PERSON_SEARCH_RUN_MIGRATION_INTEGRATION = "1"
$env:PERSON_SEARCH_POSTGRES_DSN = "postgresql+psycopg://.../disposable_database"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_processing_schema.py -v
```

Test tự chạy `downgrade base`, `upgrade head`, `alembic check`, kiểm tra constraint và
downgrade. Không trỏ DSN này tới database có dữ liệu cần giữ.
