# Person Search

Ứng dụng tìm kiếm người qua camera/video bằng mô tả văn bản hoặc ảnh truy vấn. Hệ thống gồm:

- `frontend`: React + Vite.
- `backend`: Flask API, background worker và pipeline AI.
- `infra`: PostgreSQL, Milvus và MinIO chạy bằng Docker Compose.

## Yêu cầu

Cài đặt trước:

- Git.
- Python 3.11 trở lên.
- Node.js 24.11.1 trở lên và npm.
- Docker Desktop (hoặc Docker Engine + Compose v2).
- FFmpeg có trong `PATH` nếu chạy pipeline video.
- Khuyến nghị tối thiểu 16 GB RAM và 20 GB ổ đĩa trống.

Các lệnh bên dưới dành cho Windows PowerShell và được chạy từ thư mục gốc repository.

## 1. Clone project

```powershell
git clone git@github.com:huy-nguyencong/capstone_project_new.git
cd capstone_project_new
```

## 2. Khởi động database và object storage

```powershell
Copy-Item infra/.env.example infra/.env
.\scripts\storage.ps1 validate
.\scripts\storage.ps1 up
```

Lần chạy đầu Docker sẽ tải các image cần thiết. Khi hoàn tất, PostgreSQL, Milvus và MinIO phải vượt qua smoke check.

## 3. Cài backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ai-ultralytics,ai-rasa]"
Copy-Item .env.example .env
```

Nếu PowerShell chặn script kích hoạt virtual environment, không cần đổi execution policy; có thể gọi trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,ai-ultralytics,ai-rasa]"
```

## 4. Tải checkpoint RaSa

Checkpoint lớn không được lưu trong Git, tương tự như `node_modules` không được lưu cùng source code.

1. Tải checkpoint CUHK-PEDES từ [nguồn chính thức của RaSa](https://drive.google.com/file/d/1BC1L-5JuIXHt6NR_l2ENHG3NZhncU91s/view).
2. Đổi tên file thành `rasa_cuhk_pedes_v1.pth`.
3. Đặt file tại:

```text
backend/config/model_artifacts/rasa_cuhk_pedes_v1.pth
```

Kiểm tra file tải về:

```powershell
Get-FileHash config/model_artifacts/rasa_cuhk_pedes_v1.pth -Algorithm SHA256
```

SHA-256 hợp lệ:

```text
BC85DA09C2991D5DE503C2C2AC4F032E20CC536FEC5094F0ACFF45E93D0104D2
```

Nếu hash khác, không sử dụng file và hãy tải lại. File `*.pth` đã nằm trong `.gitignore`, vì vậy không dùng `git add -f` để commit checkpoint.

## 5. Cấu hình và khởi tạo backend

Hai file mẫu `infra/.env.example` và `backend/.env.example` đã dùng cùng credential development. Sau khi tạo `.env`, chạy:

```powershell
python -m alembic upgrade head
python -c 'from dotenv import load_dotenv; load_dotenv(".env"); from person_search.storage.postgres.seed import main; main()'
```

Tài khoản development được seed:

| Username | Password |
| --- | --- |
| `admin` | `password` |
| `operator` | `password` |
| `viewer` | `password` |

Chỉ sử dụng các tài khoản này trong môi trường local.

Khởi động API:

```powershell
python -m person_search
```

API mặc định chạy tại `http://127.0.0.1:5000`. Kiểm tra ở terminal khác:

```powershell
curl.exe http://127.0.0.1:5000/health/live
curl.exe http://127.0.0.1:5000/health/ready
```

## 6. Cài và chạy frontend

Mở terminal mới tại thư mục gốc repository:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Mở URL được Vite in ra terminal, thông thường là `http://localhost:5173`.

Nếu đổi port backend, cập nhật `VITE_API_PROXY_TARGET` trong `frontend/.env` rồi khởi động lại Vite.

## Chạy lại project hằng ngày

Terminal 1, từ thư mục gốc:

```powershell
.\scripts\storage.ps1 up
```

Terminal 2:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m person_search
```

Terminal 3:

```powershell
cd frontend
npm run dev
```

## Kiểm tra code

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -m unit
.\.venv\Scripts\python.exe -m ruff check .
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

## Lỗi thường gặp

| Lỗi | Cách xử lý |
| --- | --- |
| Docker service chưa sẵn sàng | Mở Docker Desktop, sau đó chạy lại `.\scripts\storage.ps1 up`. |
| `ModuleNotFoundError: person_search` | Chạy lại `python -m pip install -e ".[dev,ai-ultralytics,ai-rasa]"` trong `backend`. |
| `/health/ready` trả về 503 | Chạy `.\scripts\storage.ps1 status` và kiểm tra `backend/.env`. |
| RaSa báo thiếu artifact | Kiểm tra đúng tên file, thư mục và SHA-256 ở bước 4. |
| `npm` từ chối phiên bản Node | Cài Node.js 24.11.1 trở lên. |
| Port 5000 đang được sử dụng | Đổi `PERSON_SEARCH_PORT` trong `backend/.env` và đổi `VITE_API_PROXY_TARGET` tương ứng. |

Tài liệu chi tiết: [backend](backend/README.md), [hạ tầng](infra/README.md), [integration tests](backend/tests/integration/README.md).
