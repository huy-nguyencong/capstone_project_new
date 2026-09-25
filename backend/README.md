# Person Search Backend

Flask API và background worker cho ứng dụng tìm kiếm người qua camera.

Repository hiện có skeleton API và lớp kết nối ba kho dữ liệu. Chưa có endpoint nghiệp vụ,
schema database hoặc mã suy luận AI.

## Yêu cầu

- Python 3.11 trở lên
- PowerShell hoặc shell tương đương

## Cài đặt môi trường phát triển

Từ thư mục `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Không commit thư mục `.venv` hoặc file `.env`.

Sao chép `backend/.env.example` thành `backend/.env` và giữ credential đồng bộ với `infra/.env`.
Entrypoint development tự đọc file này; môi trường production phải cấp biến môi trường từ secret
manager. Ứng dụng development/production từ chối khởi động nếu thiếu cấu hình storage.

## Chạy API phát triển

```powershell
python -m person_search
```

Mặc định API lắng nghe tại `http://127.0.0.1:5000`. Server tích hợp của Flask chỉ dành
cho phát triển; cấu hình WSGI phục vụ demo/triển khai sẽ được bổ sung ở task BE-25.

Các endpoint skeleton:

- `GET /health/live`
- `GET /health/ready`
- `GET /health/storage`
- `GET /api/v1/ping`

## Xác thực và tài khoản

API dùng session phía server: `POST /api/v1/auth/login` đặt cookie `ps_session` (HttpOnly) và trả
`csrf_token`; mọi request `POST/PUT/PATCH/DELETE` cần header `X-CSRF-Token`. `GET /api/v1/auth/me`
trả người dùng hiện tại, `POST /api/v1/auth/logout` thu hồi phiên.

Chưa có API quản lý tài khoản (BE-05), nên tạo Admin và tài khoản test bằng CLI sau khi migrate và seed:

```bash
python -m alembic upgrade head
person-search-seed
person-search-user create --username admin --display-name "Quản trị" --role ADMIN
person-search-user create --username khoa.tran --display-name "Trần Minh Khoa" --role OPERATOR --area GATE-A
person-search-user create --username lan.nguyen --display-name "Nguyễn Thị Lan" --role VIEWER
person-search-user set-password --username admin
```

Mật khẩu được hỏi qua prompt, hoặc lấy từ `PERSON_SEARCH_NEW_USER_PASSWORD` khi chạy script.
Thời hạn phiên cấu hình bằng `PERSON_SEARCH_SESSION_TTL_MINUTES` (mặc định 720) và
`PERSON_SEARCH_SESSION_IDLE_MINUTES` (mặc định 30). Cookie có cờ `Secure` ngoài môi trường
development; ghi đè bằng `PERSON_SEARCH_COOKIE_SECURE`.

Trên macOS, port 5000 thường bị AirPlay Receiver chiếm. Khi đó đặt `PERSON_SEARCH_PORT=5050` và
`VITE_API_PROXY_TARGET=http://127.0.0.1:5050` trong `frontend/.env`.

## Chạy kiểm thử

```powershell
python -m pytest -m unit
python -m pytest --cov=person_search --cov-report=term-missing
python -m compileall src
python -m ruff check .
```

Các test `integration`, `security` và `e2e` sẽ được bổ sung theo từng task trong
`../files/backend_implementation_plan.md`.

Khi storage stack đang chạy và đã có `backend/.env`, chạy integration test bằng:

```powershell
$env:PERSON_SEARCH_RUN_INTEGRATION = "1"
python -m pytest -m integration
```

`GET /health/ready` trả HTTP 503 nếu bất kỳ kho bắt buộc nào lỗi và giữ riêng trạng thái
`postgres`, `milvus`, `minio`; nội dung lỗi trả về không chứa credential.

## Database migrations

```powershell
$env:PERSON_SEARCH_POSTGRES_DSN = "postgresql+psycopg://..."
python -m alembic upgrade head
python -m alembic current
```

Xem `migrations/README.md` và `../docs/storage/postgres-identity-schema.md` trước khi downgrade.

Từ thư mục gốc repository, có thể chạy toàn bộ kiểm tra nhanh bằng một trong hai lệnh:

```powershell
.\scripts\check.ps1
```

```bash
./scripts/check.sh
```

## Background worker

```powershell
person-search-worker
```

Ở BE-00, command này chỉ xác nhận entrypoint đã được cài đặt. Vòng lặp xử lý job sẽ được
hiện thực ở BE-10 và không chạy bên trong request Flask.
