# Project scripts

- `check.ps1`: kiểm tra nhanh trên PowerShell/Windows.
- `check.sh`: kiểm tra nhanh trên Linux/macOS/CI.

Hai script chạy cùng một chuỗi: unit tests, Ruff và compile toàn bộ package. Integration và
E2E tests không được chạy ngầm vì cần Docker stack riêng.
