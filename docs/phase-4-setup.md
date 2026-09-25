# Phase 4 — Upload video và processing job

## Chạy demo

1. Trong `backend/`: `pip install -e '.[dev]'`, `alembic upgrade head`. Cài `ffmpeg`/`ffprobe` vào PATH. PostgreSQL, MinIO (bucket đã tạo) và Milvus cần chạy theo storage runbook.
2. API và worker dùng cùng biến môi trường storage và **cùng đường dẫn tuyệt đối** `PERSON_SEARCH_VIDEO_STAGING`. Thư mục nằm ngoài web root, ngoài Git, trên filesystem private; mặc định `var/videos` tương đối working directory. File có tên ngẫu nhiên, quyền 0600, thư mục tạo mới 0700.
3. Đặt `PERSON_SEARCH_MODEL_REGISTRY` trỏ tới `backend/config/models.demo.json`, restart API, đăng nhập Admin → Mô hình AI → áp dụng Detector/Tracker demo. Thêm camera (không cần RTSP), bật AI.
4. Chạy riêng `person-search-worker --demo` (hoặc `python -m person_search.workers.main --demo`). API không decode/chạy AI để xử lý job; request chỉ staging và kiểm tra video có đọc được.
5. Mở **Xử lý video**, chọn camera, video, thời điểm bắt đầu ghi theo giờ địa phương và sampling (mặc định 10). UI chuyển thời gian thành UTC, hiển thị tiến độ upload, sau đó poll job mỗi 3 giây. Chọn dòng để xem chi tiết/lỗi.

Demo **không nhận diện người thật**: detector sinh box giữa frame, tracker gom 5 frame lấy mẫu, encoder sinh vector deterministic. Encoder `fake_demo_v1`, collection/alias Milvus demo riêng, không ghi vào alias encoder RaSa thật. UI gắn nhãn “Demo giả lập”. CLI yêu cầu `--demo` rõ ràng; cấu hình production không được xử lý bằng fake. Các interface `FrameSource`, `Detector`, `Tracker`, `Encoder` và `Pipeline` là chỗ tích hợp adapter AI thật ở bước sau. Phase này nhận nguồn FILE; interface frame có thể mở rộng cho RTSP, chưa khởi chạy RTSP worker.

## Quy ước đã chốt

- Trạng thái theo roadmap/schema hiện có: `PENDING` (hàng đợi), `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
- Video MP4/MKV/AVI, mặc định tối đa **500 MiB** (`PERSON_SEARCH_VIDEO_MAX_BYTES`); giữ tối thiểu **1 GiB** trống (`PERSON_SEARCH_VIDEO_RESERVE_BYTES`). MIME từ browser không đáng tin; backend kiểm tra signature, container và thử decode. Giới hạn độ phân giải 3840×2160; probe/decode kiểm tra tối đa 10 giây mỗi bước. Multipart được spool; staging copy theo chunk 1 MiB, không đọc toàn video vào RAM. Reverse proxy cần giới hạn body/timeout tương ứng.
- Upload cần `Idempotency-Key` 8–128 ký tự. Scope theo Admin. Cùng key và cùng camera/thời điểm/sampling/nội dung file → cùng job (202), kể cả job đã kết thúc; đổi nội dung với cùng key → 409. Retry phải gửi lại file để kiểm chứng digest. Key trên UI được giữ qua lỗi request, đổi khi người dùng đổi dữ liệu.
- Job chụp `ai_config_version_id` tại lúc nhận; thay cấu hình sau đó không thay đổi job đang chờ/chạy. Thời điểm ghi video là nguồn mốc UTC; timestamp frame từ PTS thật, chuẩn hóa theo frame đầu tiên. `source_frame_index` được lưu ở track đại diện, sampling theo index trước Detector/Tracker.
- Cancel pending: chuyển CANCELLED ngay. Cancel running: đặt `cancel_requested`, worker dừng tại checkpoint tiếp theo; thao tác ingestion đang chạy có thể hoàn tất. Tắt AI/retire camera cũng hủy job ở checkpoint tiếp theo. Không xóa track đã READY.
- Một PostgreSQL advisory lock cho toàn worker đảm bảo concurrency 1 giữa nhiều tiến trình. Claim bằng row lock + lease token; heartbeat mỗi frame, lease 60 giây. Lease hết hạn chỉ được reclaim khi global worker lock được giải phóng.
- Worker crash → replay video từ đầu, ID track deterministic nên không nhân đôi track. Tối đa 3 lần chạy, lần claim tiếp theo đánh dấu FAILED. Supervisor giết subprocess bị treo sau `PERSON_SEARCH_JOB_TIMEOUT_SECONDS` (mặc định 3600). SIGTERM/SIGINT đóng tracker/frame source, để lease phục hồi ở lần chạy sau. `--once --demo` chạy một job phục vụ test/debug; dùng supervisor mặc định cho deadline cứng.
- Track phải READY thì job mới thành công. Nếu storage chưa READY sau ingestion/resume, job FAILED với code chung; track outbox vẫn được giữ để storage maintenance phục hồi theo cơ chế sẵn có. Không có endpoint retry job FAILED trong phase này; Admin upload lại với key mới.
- Xóa staging ngay sau trạng thái kết thúc. Worker định kỳ đối soát file terminal còn sót; file upload mồ côi chỉ xóa sau 24 giờ. File của PENDING/RUNNING không bị xóa. Không xóa frame/embedding/track trong cleanup staging.
- API không công khai source path, credential, lease token hay exception nội bộ. Audit `job.created`, `job.cancel_requested`, `job.finished`.

## API

- `POST /api/v1/admin/cameras/{id}/processing-jobs`: multipart `file`, `recorded_started_at` ISO 8601 có timezone, `sampling_interval` 1–1000; header `Idempotency-Key`; 202.
- `GET /api/v1/admin/processing-jobs`: `camera_id`, `status`, `limit` (1–100), `cursor`; mới nhất trước.
- `GET /api/v1/admin/processing-jobs/{id}`.
- `POST /api/v1/admin/processing-jobs/{id}/cancel`: idempotent, 200.

Cả bốn route chỉ Admin; mutation cần CSRF. Job có camera/source/status, frame/progress/track counts, thời gian và lỗi như roadmap; thêm `sampled_frames`, `tracks_pending`, `cancel_requested`, `pipeline_mode`. `total_frames` có thể null, dùng số thực tế khi thành công. [OpenAPI Phase 4](openapi-phase-4.json).

## Kiểm thử

- `pytest tests/unit` kiểm tra file giả, size/quota, gián đoạn, cleanup và timeout.
- Migrate **database tạm**, đặt `PERSON_SEARCH_CAMERA_TEST_DSN`, chạy `pytest tests/integration/test_video_jobs.py`. Cần ffmpeg trong PATH. Test dùng PostgreSQL thật, video tổng hợp thật, decoder PyAV thật, fake AI + frame/vector stores in-memory qua `TrackIngestionService`; không yêu cầu MinIO/Milvus cho bộ test này.
- Test sampling 10/20, UTC, READY, quyền/CSRF, idempotency, cancel, global lock, lease recovery, crash sau khi đã lưu track (không tạo trùng), tắt AI và lỗi component được sanitize. Kiểm tra môi trường triển khai vẫn cần MinIO/Milvus thật.
