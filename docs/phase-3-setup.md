# Phase 3 — Camera và cấu hình AI

## Chạy

Trong `backend/`, cài dependency `pip install -e '.[dev]'`, rồi chạy `alembic upgrade head` trên database của môi trường cần dùng. Migration `20260925_0007` thêm camera version, thời điểm kiểm tra và credential mã hóa. Không sửa/xóa track, job hoặc Case hiện có.

- `PERSON_SEARCH_RTSP_KEY`: khóa Fernet 32 byte dạng URL-safe base64. Tạo bằng `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`, lưu ngoài Git, giữ ổn định qua restart. Không có khóa vẫn dùng camera file-only và RTSP không credential được; gửi credential trả `503`.
- `PERSON_SEARCH_RTSP_NETWORKS`: CIDR camera được phép kết nối, phân cách bằng dấu phẩy. Mặc định không cho phép mạng nào. Probe chỉ nhận IP literal, chặn hostname để tránh DNS rebinding, luôn chặn loopback/link-local/multicast/unspecified. RTSP URL không nhận query string vì có thể chứa secret. Nếu cần hostname/query của nhà sản xuất, cần adapter riêng với kiểm soát tương đương.
- Cài `ffprobe` trên máy chủ để kiểm tra stream video thật. Probe dùng TCP, deadline 10 giây; timeout/không có video → `OFFLINE`, thiếu binary → `ERROR`. Không đưa stderr của ffprobe vào response hoặc audit.
- `PERSON_SEARCH_MODEL_REGISTRY`: đường dẫn JSON tin cậy do người vận hành quản lý, đọc lúc khởi động. Mẫu ở `backend/config/models.example.json`. Không có registry → danh sách rỗng, không cho bật AI khi chưa có active config. Chỉ đánh dấu model `available: true` khi đã chuẩn bị adapter/artifact phù hợp. Encoder cần `name`, `version`, `dimension`, `checkpoint_sha256` (64 ký tự hex); API không công khai checksum.

## Hành vi

- Tạo camera cần code, name, area UUID; RTSP tùy chọn. Code duy nhất, chuẩn hóa viết hoa. PATCH chỉ đổi name/RTSP và bắt buộc version; area bất biến. Để nguyên RTSP khi sửa sẽ không gửi lại URL masked; chọn thay RTSP và để trống để xóa kết nối.
- Nút “Lưu và kiểm tra RTSP” lưu camera trước, sau đó gọi connection test theo ID. Test thất bại không làm mất camera vừa lưu.
- Retire idempotent, tắt `ai_enabled` và giữ nguyên lịch sử. Bật AI cho camera file-only hợp lệ khi có config.
- `ai_enabled` là quyền nhận tác vụ mới. Không tạo worker trong Phase 3, không báo RUNNING giả. Job/worker và chính sách dừng tác vụ đang chạy thuộc Phase 4.
- Config được lưu như phiên bản mới trong `ai_config_versions`; version API là chuỗi opaque. Khi chưa có config: các field là `null`, PUT đầu tiên gửi `version: null`. Advisory lock serialize cả lần apply đầu tiên; version cũ trả 409. Cấu hình cũ chuyển RETIRED, không bị sửa nội dung nên job/track giữ tham chiếu cũ.
- Apply hiện tại xác thực registry và publish cấu hình trong transaction. Điểm tích hợp `apply_config` cho adapter chuẩn bị model phải không thay đổi worker đang chạy; lỗi rollback và ghi audit failure. Worker Phase 4 sẽ lấy active config cho tác vụ mới.
- Bốn màn hình Camera/CameraDialog/Xử lý AI/Mô hình AI dùng API thật. Các màn giám sát và chẩn đoán còn lại chuyển ở Phase 8.

## Kiểm thử

Unit tests: `pytest tests/unit`. Integration: migrate một database **tạm riêng**, rồi đặt `PERSON_SEARCH_CAMERA_TEST_DSN` và chạy `pytest tests/integration/test_camera_admin.py`. Test tạo dữ liệu riêng bằng UUID; không chạy trên production. Có kiểm tra toàn bộ 10 route với anonymous/operator/viewer, CSRF, file-only, mã trùng, credential, area bất biến, retire, pagination, idempotency, rollback và apply đồng thời. Probe network được stub trong integration; unit test kiểm tra timeout/allowlist. Cần camera thật để xác minh kết nối tại môi trường triển khai.

API contract: [openapi-phase-3.json](openapi-phase-3.json).
