# Runbook vận hành, backup/restore và bảo mật lưu trữ (STO-19)

> **Trạng thái:** restore drill nhỏ đã chạy thành công ngày 2026-09-25 trên database tạm với ba
> track/frame. Cần lặp lại với dữ liệu demo đầy đủ trước release để chốt RTO vận hành.

Lệnh POSIX dùng `sh scripts/storage.sh`; trên Windows dùng `scripts/storage.ps1` tương ứng. Lệnh
Python chạy trong `backend/` với virtualenv đã cài (`.venv/bin/python` hoặc
`.venv\Scripts\python.exe`).

## 1. Khởi động, dừng, kiểm tra

| Việc | Lệnh |
| --- | --- |
| Kiểm tra cấu hình Compose | `sh scripts/storage.sh validate` |
| Khởi động + smoke check | `sh scripts/storage.sh up` |
| Trạng thái container | `sh scripts/storage.sh status` |
| Log một service | `sh scripts/storage.sh logs milvus` |
| Dừng (giữ volume) | `sh scripts/storage.sh down` |
| Health qua API | `GET /health/ready`, `GET /health/storage` |

Không chạy `docker compose down --volumes` nếu chưa có backup đã verify.

## 2. Migrate và seed

```sh
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
.venv/bin/person-search-seed
```

Seed idempotent, tạo `admin`, `operator`, `viewer` với password `password`, và không ghi đè tài
khoản đã tồn tại. Đây là credential local/demo; seed từ chối chạy trong production.

## 3. Retry, dead-letter, reconciliation

| Việc | Lệnh | Ghi chú |
| --- | --- | --- |
| Chạy retry outbox | `person-search-storage retry-outbox --limit 50` | Exit 1 nếu có lỗi không bắt được |
| Đưa track `FAILED` về `PENDING` | `person-search-storage requeue-track <track_id> --actor-user-id <admin>` | Ghi audit |
| Reconcile dry-run | `person-search-storage reconcile` | Exit 2 nếu có sai lệch |
| Xóa orphan | `person-search-storage reconcile --delete-orphans --actor-user-id <admin>` | Chỉ sau khi đọc dry-run |
| Dựng lại Milvus | `person-search-storage reindex` | Từ embedding trong outbox |

Quy trình cho event `DEAD`:

1. Xem `failure_code` của track (`FRAME_UPLOAD_FAILED`, `VECTOR_UPSERT_FAILED`, ...) và
   `StorageStatusService` hoặc log để biết component nào lỗi.
2. Sửa nguyên nhân (dịch vụ chết, đầy đĩa, credential sai).
3. `requeue-track`, rồi `retry-outbox`.
4. Nếu lỗi là frame thiếu trên MinIO, worker không tự upload được: cho AI worker gửi lại track
   cùng `track_id`.

## 4. Backup

```sh
cd backend
.venv/bin/python tools/storage_backup.py backup            # ghi vào <repo>/backups/<UTC>/
.venv/bin/python tools/storage_backup.py verify ../backups/<UTC>
```

Nội dung một bản backup:

| Thành phần | Cách lấy | File |
| --- | --- | --- |
| PostgreSQL | `pg_dump -Fc` trong container `postgres` | `postgres.dump` |
| Full frame MinIO | Đọc theo `person_tracks.minio_object_key`, kiểm tra SHA-256 khi đọc | `frames/…`, `frames.json` |
| Milvus | Không copy; dựng lại từ `storage_outbox_events.payload.embedding` có trong dump | — |
| Manifest | Phiên bản manifest, alembic revision, `pg_dump --version`, SHA-256 `compose.yaml`, số track theo status, SHA-256 và kích thước từng file, thời gian mỗi pha | `manifest.json` |

Lý do không dùng `mc mirror` ra thư mục local: cách đó làm mất metadata `sha256` của object, trong
khi adapter bắt buộc có metadata này khi đọc ảnh. Object không thuộc track nào (orphan) không được
backup.

Lý do không backup Milvus: vector là dữ liệu dẫn xuất và embedding gốc đã nằm trong PostgreSQL.
Đổi lại, RTO bao gồm thời gian reindex (đo ở mục 7). Nếu sau này xóa embedding khỏi outbox, phải
chuyển sang `milvus-backup` hoặc snapshot volume `milvus_data` + `etcd_data` + bucket `a-bucket`.

Thư mục `backups/` đã có trong `.gitignore`. Bản backup chứa ảnh người và hash mật khẩu: lưu trên
đĩa được mã hóa, không đồng bộ lên dịch vụ công cộng, xóa bản cũ theo chính sách giữ bản.

## 5. Restore

Thứ tự bắt buộc, vì PostgreSQL là nguồn sự thật:

1. `verify` checksum toàn bộ bản backup.
2. PostgreSQL: `pg_restore --clean --if-exists --no-owner --single-transaction`, sau đó đối chiếu
   alembic revision với manifest.
3. MinIO: upload lại từng frame kèm metadata `track-id` và `sha256`; bỏ qua object đã có đúng
   checksum.
4. Milvus: `ensure_collection` rồi `StorageReindexer` cho mọi track `READY`, có đọc lại để xác
   nhận.
5. Reconcile dry-run. Restore chỉ thành công (exit 0) khi reindex sạch và không có object/vector
   thiếu hoặc checksum sai.

```sh
sh scripts/storage.sh up
cd backend
.venv/bin/python tools/storage_backup.py restore ../backups/<UTC> --yes
```

`--yes` là bắt buộc vì restore thay toàn bộ database hiện tại.

## 6. Restore drill (bắt buộc trước demo)

1. Trên stack đang có dữ liệu: `tools/storage_backup.py backup`, rồi `verify`.
2. Ghi lại: số track `READY`, một `track_id`, một `case_result_id`.
3. Tạo stack trống. Chỉ làm bước này khi bản backup đã verify:
   `docker compose --env-file infra/.env -f infra/compose.yaml down --volumes`, rồi
   `sh scripts/storage.sh up`.
4. `tools/storage_backup.py restore <dir> --yes`, lưu JSON kết quả.
5. Kiểm tra lại luồng: search bằng Operator ra track đã ghi, mở crop/full frame, mở Case bằng
   Viewer. Có thể chạy `PERSON_SEARCH_RUN_E2E=1 pytest -m e2e` trên một database test riêng.
6. Điền kết quả vào mục 7.

## 7. RPO/RTO

| Chỉ số | Giá trị | Cách đo |
| --- | --- | --- |
| RPO | Bằng khoảng cách giữa hai lần backup (backup chạy thủ công trong phạm vi đồ án) | Lịch backup thực tế |
| Thời gian backup | 0,906 giây (drill 3 track/frame) | `postgres_dump` 0,848 giây + `frames_export` 0,058 giây |
| RTO: PostgreSQL restore | 0,385 giây (drill) | `timings_seconds.postgres_restore` |
| RTO: frame restore | 0,040 giây (drill) | `timings_seconds.frames_restore` |
| RTO: Milvus reindex | 4,975 giây (drill) | `timings_seconds.milvus_reindex` |
| RTO tổng (không tính dựng stack) | 5,522 giây (drill) | `total_seconds` |
| Kích thước backup | chưa đo | tổng `bytes` trong manifest |

## 8. Đầy đĩa

Dấu hiệu: ingestion chuyển nhiều track sang `PENDING`/`FAILED` với `FRAME_UPLOAD_FAILED` hoặc
`VECTOR_UPSERT_FAILED`, PostgreSQL báo `No space left on device`, Milvus/etcd restart.

1. Dừng AI worker để ngừng tạo track mới. Không xóa volume.
2. `docker system df -v` để xem volume nào lớn; dọn image/container/build cache không dùng
   (`docker image prune`, `docker builder prune`), không prune volume.
3. Xóa bản backup cũ đã có bản mới được verify, hoặc chuyển chúng sang ổ khác.
4. Reconcile dry-run; nếu có orphan do lỗi giữa chừng thì xem xét `--delete-orphans`.
5. Khởi động lại stack, `retry-outbox`, `requeue-track` cho track `FAILED`.
6. Etcd báo vượt quota (`ETCD_QUOTA_BACKEND_BYTES` = 4 GB): chạy compaction/defrag theo tài liệu
   etcd trước khi khởi động lại Milvus.

## 9. Bảo mật

- **Least privilege:** backend dùng user MinIO `person-search-app`, chỉ có quyền
  Get/Put/Delete/List trên bucket `person-search-frames` (`infra/minio/app-policy.json`). Root
  credential chỉ dùng cho quản trị và Milvus. Nên tạo role PostgreSQL riêng cho ứng dụng, không
  phải superuser, khi triển khai ngoài máy dev.
- **Network exposure:** mọi cổng Compose chỉ bind `127.0.0.1`. Không mở cổng PostgreSQL, MinIO,
  Milvus, etcd ra LAN/Internet; chỉ Flask API (qua reverse proxy) được public.
- **TLS ngoài local:** đặt reverse proxy (Caddy hoặc Nginx) có TLS trước Flask; bật
  `PERSON_SEARCH_MINIO_SECURE=true` với chứng chỉ MinIO; PostgreSQL dùng `sslmode=require`
  trong DSN; Milvus bật TLS và token (`PERSON_SEARCH_MILVUS_TOKEN`).
- **Xoay credential:**
  - PostgreSQL: `ALTER ROLE ... PASSWORD ...`, cập nhật `infra/.env` và
    `PERSON_SEARCH_POSTGRES_DSN`, restart API/worker.
  - MinIO app user:
    `mc admin user add storage person-search-app <secret-mới>` (ghi đè secret), cập nhật
    `MINIO_APP_SECRET_KEY` và `PERSON_SEARCH_MINIO_SECRET_KEY`, restart API/worker. Sửa `.env`
    thôi không đổi secret đang lưu trong MinIO.
  - MinIO root: đổi `MINIO_ROOT_*` cần cập nhật đồng thời Milvus (`MINIO_ACCESS_KEY_ID`,
    `MINIO_SECRET_ACCESS_KEY`) rồi `up` lại cả stack.
- **Secret trong repo:** chỉ file `.env.example` với giá trị dev. Audit log redact password, token,
  credential trong URL, vector và ảnh (xem `audit-and-status.md`).
