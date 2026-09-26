# Person Search

Ứng dụng tìm kiếm người qua camera/video bằng mô tả văn bản hoặc ảnh truy vấn. Hệ thống gồm:

- `frontend`: React + Vite.
- `backend`: Flask API, background worker và pipeline AI.
- `infra`: PostgreSQL, Milvus và MinIO chạy bằng Docker Compose.

Tài liệu này mô tả một quy trình duy nhất để chạy ứng dụng end-to-end trên Windows phục vụ phát
triển và demo local: storage → database → AI preflight → worker → API → frontend.

## Yêu cầu

- Git.
- Python 3.11 trở lên.
- Node.js 24.11.1 trở lên và npm.
- Docker Desktop (hoặc Docker Engine + Compose v2).
- FFmpeg và `ffprobe` có trong `PATH`.
- Khuyến nghị tối thiểu 16 GB RAM và 20 GB ổ đĩa trống.

Các lệnh bên dưới dành cho Windows PowerShell. Nếu chưa clone project:

```powershell
git clone git@github.com:huy-nguyencong/capstone_project_new.git
cd capstone_project_new
```

## A. Thiết lập lần đầu

### 1. Chuẩn bị storage

Chạy từ thư mục gốc repository:

```powershell
Copy-Item infra/.env.example infra/.env
.\scripts\storage.ps1 validate
.\scripts\storage.ps1 up
```

Lần chạy đầu Docker sẽ tải image. Lệnh `up` chỉ hoàn tất thành công khi PostgreSQL, Milvus và
MinIO vượt qua smoke check.

### 2. Cài backend và AI runtime

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,ai-ultralytics,ai-rasa]"
Copy-Item .env.example .env
```

Nếu PowerShell chặn script kích hoạt virtual environment, không cần đổi execution policy. Có thể
gọi trực tiếp `.\.venv\Scripts\python.exe` thay cho `python` trong các lệnh backend.

### 3. Chuẩn bị model production

YOLO11n không được lưu trong Git. Từ thư mục `backend`, tải artifact đã khai báo trong production
registry:

```powershell
New-Item -ItemType Directory -Force .\config\model_artifacts
Invoke-WebRequest `
  -Uri "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo11n.pt" `
  -OutFile .\config\model_artifacts\yolo11n.pt
Get-FileHash .\config\model_artifacts\yolo11n.pt -Algorithm SHA256
```

File YOLO11n cần nằm tại:

```text
backend/config/model_artifacts/yolo11n.pt
```

SHA-256 phải là:

```text
0EBBC80D4A7680D14987A577CD21342B65ECFD94632BD9A8DA63AE6417644EE1
```

RaSa không được lưu trong Git. Tải checkpoint CUHK-PEDES từ
[nguồn chính thức của RaSa](https://drive.google.com/file/d/1BC1L-5JuIXHt6NR_l2ENHG3NZhncU91s/view),
đổi tên thành `rasa_cuhk_pedes_v1.pth` và đặt tại:

```text
backend/config/model_artifacts/rasa_cuhk_pedes_v1.pth
```

Từ thư mục `backend`, kiểm tra checkpoint RaSa:

```powershell
Get-FileHash config/model_artifacts/rasa_cuhk_pedes_v1.pth -Algorithm SHA256
```

SHA-256 phải là:

```text
BC85DA09C2991D5DE503C2C2AC4F032E20CC536FEC5094F0ACFF45E93D0104D2
```

Nếu hash khác, không sử dụng file và hãy tải lại. Không dùng `git add -f` để commit checkpoint.

### 4. Cấu hình backend

Mở `backend/.env` và giữ `PERSON_SEARCH_ENV=development` cho demo local. Điền ba đường dẫn tuyệt
đối sau; API và worker phải dùng chung file `.env` và cùng thư mục video staging:

```dotenv
PERSON_SEARCH_MODEL_REGISTRY=D:\duong-dan\toi\project\backend\config\models.example.json
PERSON_SEARCH_MODEL_ARTIFACT_ROOT=D:\duong-dan\toi\project\backend\config
PERSON_SEARCH_VIDEO_STAGING=D:\duong-dan\toi\project\backend\var\videos
```

Không bật `PERSON_SEARCH_ALLOW_DEMO_MODELS`; registry production ở trên chạy YOLO11n, ByteTrack và
RaSa thật. Có thể lấy đường dẫn cần điền bằng PowerShell:

```powershell
(Resolve-Path .\config\models.example.json).Path
(Resolve-Path .\config).Path
New-Item -ItemType Directory -Force .\var\videos
(Resolve-Path .\var\videos).Path
```

Credential development trong `infra/.env.example` và `backend/.env.example` đã khớp nhau. Không
dùng các credential hoặc tài khoản seed này ngoài máy local.

### 5. Khởi tạo database

Vẫn tại `backend`, với virtual environment đang kích hoạt:

```powershell
python -m alembic upgrade head
python -c 'from dotenv import load_dotenv; load_dotenv(".env"); from person_search.storage.postgres.seed import main; main()'
```

Tài khoản development được seed:

| Vai trò | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `password` |
| Operator | `operator` | `password` |
| Viewer | `viewer` | `password` |

### 6. Chạy AI preflight

Preflight phải trả về `ready=true` trước khi khởi động worker:

```powershell
python tools/ai_preflight.py `
  --registry config\models.example.json `
  --resource-config config\ai_resources.json `
  --profile local_cpu
```

Nếu preflight báo thiếu artifact, sai checksum, thiếu FFmpeg, thiếu RAM/đĩa hoặc model không tương
thích thì xử lý lỗi đó trước khi tiếp tục. Loader không tự tải model từ URL trong registry.

### 7. Cài frontend

Mở terminal mới tại thư mục gốc repository:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
```

Mặc định API chạy tại `http://127.0.0.1:5000`; `frontend/.env.example` đã proxy `/api/v1` tới địa
chỉ này.

## B. Khởi chạy ứng dụng end-to-end

Mỗi thành phần chạy trong một terminal riêng. Luôn chạy lệnh từ đúng thư mục được ghi dưới đây.

### Terminal 1 — Storage

Từ thư mục gốc repository:

```powershell
.\scripts\storage.ps1 up
```

### Terminal 2 — AI worker

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
person-search-production-worker
```

Giữ terminal này chạy. Worker xử lý tuần tự job video upload và job RTSP có giới hạn frame. Nếu
worker không chạy, API và giao diện vẫn mở được nhưng job AI sẽ không được xử lý.

### Terminal 3 — Backend API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m person_search
```

API mặc định chạy tại `http://127.0.0.1:5000`. Kiểm tra ở terminal khác:

```powershell
curl.exe http://127.0.0.1:5000/health/live
curl.exe http://127.0.0.1:5000/health/ready
```

`/health/live` và `/health/ready` phải trả về thành công; màn hình trạng thái hệ thống phải hiển
thị worker có heartbeat mới (`IDLE` khi chưa có job).

### Terminal 4 — Frontend

```powershell
cd frontend
npm run dev
```

Mở URL Vite in ra terminal, thông thường là `http://localhost:5173`.

Nếu đổi `PERSON_SEARCH_PORT` trong `backend/.env`, phải đổi `VITE_API_PROXY_TARGET` trong
`frontend/.env` tương ứng và khởi động lại cả API lẫn Vite.

## C. Luồng kiểm tra end-to-end trên giao diện

1. Đăng nhập bằng tài khoản `admin`.
2. Mở quản trị model, chọn/cập nhật cấu hình production dùng `yolo11n_coco` và `bytetrack_v1`.
3. Tạo camera logic trong một khu vực, áp dụng cấu hình model và bật AI cho camera.
4. Upload một video ngắn có người. Với máy CPU, chọn profile `throughput` (`N=20`) để demo nhanh;
   dùng `baseline` (`N=10`) nếu cần lấy mẫu dày hơn.
5. Theo dõi processing job cho tới khi trạng thái là `SUCCEEDED`; kiểm tra số track đã publish bằng
   số track hoàn tất.
6. Đăng nhập `operator`, tìm người bằng mô tả văn bản hoặc ảnh và mở kết quả tìm kiếm.
7. Nếu cần trình diễn luồng nghiệp vụ đầy đủ, tạo Case từ kết quả rồi đăng nhập `viewer` để kiểm tra
   quyền chỉ xem.

Không tắt worker trong khi job đang chạy. Lần inference đầu có thể chậm hơn do model được nạp vào
bộ nhớ.

## D. Dừng ứng dụng

Dừng frontend, API và worker bằng `Ctrl+C` trong từng terminal. Sau đó, từ thư mục gốc:

```powershell
.\scripts\storage.ps1 down
```

Lệnh trên dừng container nhưng không xóa volume dữ liệu.

## Kiểm tra code (tùy chọn)

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
| `/health/ready` trả về 503 | Chạy `.\scripts\storage.ps1 status`, kiểm tra `backend/.env` và log của từng storage service. |
| Worker dừng ngay khi mở | Chạy lại preflight và kiểm tra ba đường dẫn tuyệt đối trong `backend/.env`. |
| Job ở trạng thái chờ quá lâu | Kiểm tra terminal worker và heartbeat trên màn hình trạng thái hệ thống. |
| RaSa báo thiếu artifact hoặc sai checksum | Kiểm tra đúng tên file, thư mục và SHA-256 ở phần chuẩn bị model. |
| `npm` từ chối phiên bản Node | Cài Node.js 24.11.1 trở lên. |
| Port 5000 đang được sử dụng | Đổi `PERSON_SEARCH_PORT` và `VITE_API_PROXY_TARGET` tương ứng rồi khởi động lại API/Vite. |
| Hết dung lượng khi upload | Xóa file demo không cần thiết hoặc chuyển `PERSON_SEARCH_VIDEO_STAGING` sang ổ đĩa còn đủ chỗ. |

Tài liệu chuyên sâu: [backend](backend/README.md), [hạ tầng](infra/README.md),
[integration tests](backend/tests/integration/README.md) và [E2E tests](backend/tests/e2e/README.md).
