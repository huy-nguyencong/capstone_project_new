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
