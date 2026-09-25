# Person Search Backend

Flask API và background worker cho ứng dụng tìm kiếm người qua camera.

Backend dùng PostgreSQL để lưu dữ liệu nghiệp vụ, Milvus để lưu vector và MinIO để lưu ảnh.
API và database migrations đã có trong repository; pipeline AI hiện chỉ có adapter demo.

## Yêu cầu

- Python 3.11 trở lên.
- Docker Desktop/Engine đang chạy, có Docker Compose v2.
- Dành tối thiểu 4 CPU, 8 GB RAM cho Docker (khuyến nghị 16 GB RAM) và 20 GB đĩa trống.
- Terminal macOS/Linux hoặc PowerShell trên Windows.

## Khởi động lần đầu

Thứ tự: **khởi động storage → cài dependencies → cấu hình backend → migration và seed → chạy API**.
Các lệnh dưới đây bắt đầu từ thư mục gốc repository, nơi chứa `backend`, `frontend`, `infra`.

### 1. Khởi động storage

macOS/Linux:

```bash
python3 --version
docker compose version
test -f infra/.env || cp infra/.env.example infra/.env
sh scripts/storage.sh validate
sh scripts/storage.sh up
```

Windows PowerShell:

```powershell
python --version
docker compose version
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
.\scripts\storage.ps1 validate
.\scripts\storage.ps1 up
```

Lần đầu Docker cần tải image. Lệnh `up` chờ các service healthy rồi kiểm tra kết nối;
thành công khi thấy `PostgreSQL, Milvus and MinIO smoke checks passed.`
Giữ nguyên file `.env` nếu đã có cấu hình của nhóm. Chi tiết xem [hạ tầng local](../infra/README.md).

### 2. Cài môi trường Python

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
test -f .env || cp .env.example .env
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Nếu đã có `.venv` với Python phù hợp, bỏ qua lệnh tạo virtualenv. Không commit `.venv` hoặc `.env`.

### 3. Cấu hình backend

Mở `backend/.env` và giữ thông tin kết nối đồng bộ với `infra/.env`:

| Biến trong `backend/.env` | Giá trị tương ứng trong `infra/.env` |
| --- | --- |
| `PERSON_SEARCH_POSTGRES_DSN` | `postgresql+psycopg://<POSTGRES_USER>:<POSTGRES_PASSWORD>@127.0.0.1:<POSTGRES_PORT>/<POSTGRES_DB>` |
| `PERSON_SEARCH_MILVUS_URI` | `http://127.0.0.1:<MILVUS_PORT>` |
| `PERSON_SEARCH_MINIO_ENDPOINT` | `127.0.0.1:<MINIO_API_PORT>` |
| `PERSON_SEARCH_MINIO_ACCESS_KEY` | `MINIO_APP_ACCESS_KEY` |
| `PERSON_SEARCH_MINIO_SECRET_KEY` | `MINIO_APP_SECRET_KEY` |

Hai file mẫu đã khớp nhau. Dùng credential MinIO của ứng dụng, không dùng tài khoản root.
Nếu password PostgreSQL chứa ký tự đặc biệt trong URL, cần URL-encode password trong DSN.

Hướng dẫn này dùng port **5050** để tránh trùng AirPlay Receiver trên macOS. Sửa trong `backend/.env`:

```dotenv
PERSON_SEARCH_ENV=development
PERSON_SEARCH_PORT=5050
```

Nếu chạy frontend, đặt `VITE_API_PROXY_TARGET=http://127.0.0.1:5050` trong `frontend/.env`
và khởi động lại frontend dev server. Nếu giữ port mặc định `5000`, thay `5050` trong các lệnh
kiểm tra bên dưới thành `5000`.

Entrypoint API development tự đọc `.env`; production phải cấp biến môi trường từ secret manager.
Ứng dụng development/production từ chối khởi động nếu thiếu cấu hình storage.

### 4. Tạo bảng và tài khoản demo

Vẫn ở thư mục `backend`, với virtualenv đã được kích hoạt, chạy trên cả hai hệ điều hành:

```bash
python -m alembic upgrade head
python -c 'from dotenv import load_dotenv; load_dotenv(".env"); from person_search.storage.postgres.seed import main; main()'
```

Lệnh seed trên đọc `.env` trước khi tạo dữ liệu vì entrypoint `person-search-seed` hiện chưa tự
đọc file này. Seed tạo các tài khoản `admin`, `operator`, `viewer`, cùng mật khẩu `password`.
Chỉ dùng các tài khoản này cho development local.

### 5. Chạy API và kiểm tra

```powershell
python -m person_search
```

Giữ terminal này mở. API chạy tại `http://127.0.0.1:5050` nếu cấu hình theo bước 3.
Server tích hợp của Flask chỉ dành cho phát triển.

Mở terminal khác:

```bash
curl -i http://127.0.0.1:5050/health/live
curl -i http://127.0.0.1:5050/health/ready
```

Trên Windows PowerShell, dùng `curl.exe` thay cho `curl` nếu shell ánh xạ `curl` sang lệnh khác.
`/health/ready` trả **HTTP 200** khi kết nối được cả ba storage; trả **503** nếu một kho bắt buộc lỗi.

Các endpoint kiểm tra:

- `GET /health/live`
- `GET /health/ready`
- `GET /health/storage`

## Những lần chạy tiếp theo

Từ thư mục gốc repository, macOS/Linux:

```bash
sh scripts/storage.sh up
cd backend
source .venv/bin/activate
python -m person_search
```

Windows PowerShell:

```powershell
.\scripts\storage.ps1 up
cd backend
.\.venv\Scripts\Activate.ps1
python -m person_search
```

Sau khi lấy code mới có migration, chạy `python -m alembic upgrade head` trong `backend`
trước khi bật API. Không cần seed lại mỗi lần chạy.

Dừng API bằng `Ctrl+C`. Để dừng storage, từ thư mục gốc chạy `sh scripts/storage.sh down`
(PowerShell: `.\scripts\storage.ps1 down`); dữ liệu trong named volumes được giữ lại.

## Lỗi khởi động thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không tìm thấy `docker` hoặc không kết nối được Docker daemon | Cài/mở Docker Desktop, chờ Docker sẵn sàng rồi mở lại terminal. |
| `Address already in use` | Chọn port API còn trống trong `backend/.env`; cập nhật proxy frontend theo cùng port. |
| `ModuleNotFoundError: person_search` | Kích hoạt `.venv`, chạy lại `python -m pip install -e ".[dev]"` trong `backend`. |
| Thiếu cấu hình storage hoặc lỗi xác thực database | Kiểm tra `backend/.env`, đối chiếu credential và port với `infra/.env`; biến môi trường đã export được ưu tiên hơn `.env`. |
| Database báo thiếu bảng | Chạy `python -m alembic upgrade head` trong `backend`. |
| `/health/ready` trả 503 | Kiểm tra trạng thái và log storage bằng các lệnh bên dưới. |

Từ thư mục gốc, macOS/Linux:

```bash
sh scripts/storage.sh status
sh scripts/storage.sh logs
```

PowerShell: `.\scripts\storage.ps1 status` và `.\scripts\storage.ps1 logs`.
Endpoint `/health/storage` cũng cung cấp trạng thái các kho dữ liệu.

## Xác thực và tài khoản

API dùng session phía server: `POST /api/v1/auth/login` đặt cookie `ps_session` (HttpOnly) và trả
`csrf_token`; mọi request `POST/PUT/PATCH/DELETE` cần header `X-CSRF-Token`. `GET /api/v1/auth/me`
trả người dùng hiện tại, `POST /api/v1/auth/refresh` xoay token và gia hạn phiên còn hợp lệ,
`POST /api/v1/auth/logout` thu hồi phiên. Response đăng nhập, lấy thông tin phiên và refresh trả
`refresh_after_seconds` để frontend lên lịch refresh trước idle timeout.

Các username là `admin`, `operator`, `viewer`; cả ba dùng password `password`. Operator được gán
vào Area `GATE-A`. Seed idempotent, không ghi đè user đã tồn tại và từ chối chạy khi
`PERSON_SEARCH_ENV=production`. Dùng CLI `person-search-user` để tạo tài khoản khác hoặc đổi mật khẩu.
Thời hạn phiên cấu hình bằng `PERSON_SEARCH_SESSION_TTL_MINUTES` (mặc định 720) và
`PERSON_SEARCH_SESSION_IDLE_MINUTES` (mặc định 30). Cookie có cờ `Secure` ngoài môi trường
development; ghi đè bằng `PERSON_SEARCH_COOKIE_SECURE`.

## Chạy kiểm thử

```powershell
python -m pytest -m unit
python -m pytest --cov=person_search --cov-report=term-missing
python -m compileall src
python -m ruff check .
```

Xem điều kiện chạy test trong [integration README](tests/integration/README.md)
và [e2e README](tests/e2e/README.md).

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

Worker chạy riêng, không cần để khởi động API. Hiện chưa có adapter AI production;
lệnh `person-search-worker` không kèm `--demo` sẽ báo lỗi.

Để thử pipeline video demo, đặt `PERSON_SEARCH_MODEL_REGISTRY` trong `backend/.env` thành
**đường dẫn tuyệt đối** đến [config/models.demo.json](config/models.demo.json).
Đặt thêm `PERSON_SEARCH_ALLOW_DEMO_MODELS=1`; nếu artifact nằm ngoài thư mục chứa manifest,
đặt `PERSON_SEARCH_MODEL_ARTIFACT_ROOT` thành thư mục local đáng tin cậy. Demo registry bị từ
chối khi thiếu opt-in này và không thể được dùng như registry production.
API và worker cần cùng cấu hình `PERSON_SEARCH_VIDEO_STAGING`; nên dùng đường dẫn tuyệt đối
đến một thư mục private dùng chung. Khởi động lại API sau khi đổi `.env`.

Mở terminal riêng tại `backend`, kích hoạt `.venv` như trên, rồi chạy:

```bash
person-search-worker --demo
```

Pipeline demo sinh dữ liệu giả lập để kiểm thử luồng, không thực hiện nhận diện người thực tế.
Manifest production mẫu nằm tại [config/models.example.json](config/models.example.json).
Các URL trong manifest chỉ là provenance; loader không tải artifact qua mạng. `available`
được suy ra từ artifact local, checksum, phê duyệt license và kết quả preflight.
