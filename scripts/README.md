# Project scripts

- `check.ps1`: kiểm tra nhanh trên PowerShell/Windows.
- `check.sh`: kiểm tra nhanh trên Linux/macOS/CI.
- `storage.ps1`: validate/up/down/status/logs/smoke cho storage stack trên PowerShell.
- `storage.sh`: các thao tác storage tương đương trên Linux/macOS/Git Bash.

Hai script chạy cùng một chuỗi: unit tests, Ruff và compile toàn bộ package. Integration và
E2E tests không được chạy ngầm vì cần Docker stack riêng.

Xem `infra/README.md` để chuẩn bị `infra/.env`, yêu cầu tài nguyên và cách vận hành stack.
