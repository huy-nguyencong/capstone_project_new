# Project scripts

- `check.ps1`: kiểm tra nhanh trên PowerShell/Windows.
- `check.sh`: kiểm tra nhanh trên Linux/macOS/CI.
- `storage.ps1`: validate/up/down/status/logs/smoke cho storage stack trên PowerShell.
- `storage.sh`: các thao tác storage tương đương trên Linux/macOS/Git Bash.
- `demo-reset.ps1`: đưa dữ liệu demo về bản sao lưu mới nhất (hoặc `-Backup <thư mục>`) sau mỗi lần
  diễn tập: restore, xóa ảnh/vector mồ côi, `reconcile`. Dừng API/worker trước; xem
  `files/demo-script.md`.
- `test-db.ps1`: `create`/`drop`/`dsn` database dùng một lần `person_search_citest` (tạo ở migration
  head) cho integration/E2E test; in sẵn DSN để export.

Hai script chạy cùng một chuỗi: unit tests, Ruff và compile toàn bộ package. Integration và
E2E tests không được chạy ngầm vì cần Docker stack riêng.

Xem `infra/README.md` để chuẩn bị `infra/.env`, yêu cầu tài nguyên và cách vận hành stack.
