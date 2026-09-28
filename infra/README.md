# Local storage infrastructure

Docker Compose này dựng PostgreSQL, Milvus Standalone và một MinIO dùng chung cho Milvus cùng
ứng dụng. Dữ liệu ứng dụng nằm trong bucket private `person-search-frames`; backend dùng tài
khoản chỉ có quyền đọc/ghi/xóa object trong bucket đó. MinIO root credential chỉ dành cho quản
trị local và kết nối nội bộ của Milvus (bucket mặc định `a-bucket`).

## Yêu cầu tài nguyên

- Docker Desktop/Engine với Compose v2.
- Tối thiểu 4 CPU và 8 GB RAM dành cho Docker; khuyến nghị 16 GB RAM để Milvus ổn định.
- Tối thiểu 20 GB đĩa trống cho lần chạy đầu và dữ liệu thử nghiệm. Theo dõi thêm vì full frame
  và vector sẽ làm dung lượng tăng theo số track.

Đây là cấu hình phát triển một node, không phải cấu hình production. Các service trao đổi qua
network bridge riêng của Compose; các cổng phát triển chỉ bind vào `127.0.0.1`, không lắng nghe
trên toàn bộ card mạng của máy host.

## Khởi động nhanh

PowerShell:

```powershell
Copy-Item infra/.env.example infra/.env
# Đổi các password dev trong infra/.env trước khi dùng chung máy/mạng.
scripts/storage.ps1 validate
scripts/storage.ps1 up
```

Linux/macOS/Git Bash:

```sh
cp infra/.env.example infra/.env
# Đổi các password dev trong infra/.env trước khi dùng chung máy/mạng.
sh scripts/storage.sh validate
sh scripts/storage.sh up
```

`up` đợi service healthy rồi tự chạy smoke check cho PostgreSQL, Milvus và MinIO. Endpoint host:

| Service | Endpoint mặc định | Ghi chú |
| --- | --- | --- |
| PostgreSQL | `127.0.0.1:5432` | DB/user lấy từ `infra/.env` |
| Milvus gRPC | `127.0.0.1:19530` | Health HTTP ở port `9091` |
| MinIO S3 | `http://127.0.0.1:9000` | Backend dùng app credential |
| MinIO Console | `http://127.0.0.1:9001` | Đăng nhập bằng root credential local |

## Vận hành

```powershell
scripts/storage.ps1 status
scripts/storage.ps1 smoke
scripts/storage.ps1 logs                # Ctrl+C để thoát
scripts/storage.ps1 logs -Service milvus
scripts/storage.ps1 down
```

Trên shell POSIX, thay bằng `sh scripts/storage.sh <action> [service]`. Lệnh `down` dừng container
an toàn và **giữ nguyên** bốn named volume. `up` sau đó sử dụng lại dữ liệu. Không chạy
`docker compose down --volumes` nếu chưa chủ động chấp nhận xóa toàn bộ dữ liệu local; backup,
restore và xử lý sự cố lưu trữ xem mục vận hành trong `backend/README.md`.

Bucket bootstrap có thể chạy lặp lại. Nếu đổi `MINIO_APP_SECRET_KEY` sau khi user đã được tạo,
cần cập nhật credential user trong MinIO hoặc tạo lại môi trường local có chủ đích; chỉ sửa file
`.env` không tự xoay secret đang lưu trong MinIO.

## Phiên bản image

| Thành phần | Image đã pin |
| --- | --- |
| PostgreSQL | `postgres:17.11-alpine3.23` |
| Milvus | `milvusdb/milvus:v2.6.24` |
| etcd | `quay.io/coreos/etcd:v3.5.25` |
| MinIO server | `minio/minio:RELEASE.2024-12-18T13-15-44Z` |
| MinIO client/bootstrap | `minio/minio:RELEASE.2024-12-18T13-15-44Z` |
| MediaMTX (profile `rtsp`) | `bluenviron/mediamtx:1.12.3` |

Ba image Milvus/etcd/MinIO bám theo manifest standalone chính thức của Milvus 2.6.24. Container
bootstrap tái sử dụng lệnh `mc` có sẵn trong image MinIO để không phụ thuộc một image client
khác; không tự nâng riêng dependency trước khi chạy lại integration test.
