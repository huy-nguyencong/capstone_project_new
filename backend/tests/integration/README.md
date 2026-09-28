# Integration tests

Các test trong thư mục này sử dụng PostgreSQL, Milvus hoặc MinIO thật từ Docker Compose.
Chúng được đánh dấu `pytest.mark.integration` và không chạy trong bộ unit test nhanh.

Hạ tầng integration test được dựng ở `STO-02`; `STO-03` bổ sung smoke test kết nối thật cho
PostgreSQL, Milvus và MinIO. Test chỉ chạy khi đặt `PERSON_SEARCH_RUN_INTEGRATION=1` và đã export
các biến storage trong `backend/.env.example`.

Migration test STO-04 cần thêm `PERSON_SEARCH_RUN_MIGRATION_INTEGRATION=1` và DSN trỏ tới một
database dùng một lần. Test tự chạy `downgrade base → upgrade head → alembic check → constraint
checks → downgrade base`, nhưng không tự tạo hoặc xóa database bên ngoài DSN được cung cấp.

STO-05 dùng cùng cơ chế qua `test_processing_schema.py`, bổ sung kiểm tra bbox, sampling interval,
artifact `READY`, state transition và rollback riêng về revision `20260925_0001`.

**Chặn nhầm database demo (R2).** `tests/conftest.py` dừng pytest ngay (exit 4) nếu bật `PERSON_SEARCH_RUN_MIGRATION_INTEGRATION`, `PERSON_SEARCH_RUN_ADAPTER_INTEGRATION`, `PERSON_SEARCH_RUN_E2E` hoặc đặt `PERSON_SEARCH_CAMERA_TEST_DSN` mà tên database trong DSN tương ứng không kết thúc bằng `_test`/`_citest`. Lưu ý test gọi `load_dotenv()`, nên nếu không export DSN riêng thì DSN demo trong `backend/.env` sẽ được dùng và bị chặn.

Tạo database dùng một lần (ở migration head) và lấy DSN để export:

```powershell
.\scripts\test-db.ps1 create   # xóa nếu có, tạo person_search_citest, alembic upgrade head
$env:PERSON_SEARCH_POSTGRES_DSN = '<DSN in ra>'
$env:PERSON_SEARCH_CAMERA_TEST_DSN = '<DSN in ra>'
.\scripts\test-db.ps1 drop     # dọn sau khi chạy xong
```

Migration test và E2E kết thúc bằng `downgrade base`; muốn chạy tiếp nhóm PostgreSQL worker thì chạy lại `test-db.ps1 create`. MinIO/Milvus vẫn dùng chung với demo nhưng test dùng collection/alias riêng và tự dọn object của mình.
