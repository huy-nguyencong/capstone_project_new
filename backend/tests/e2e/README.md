# End-to-end tests

`test_storage_workflow.py` chạy kịch bản STO-17 trên PostgreSQL, MinIO và Milvus thật:
seed hai area → ingest track `READY` → search theo area → crop/full frame → Case lưu cùng track
hai lần → sửa Case hai lần liên tiếp → đổi area Operator → Viewer và dashboard → MinIO/Milvus
unavailable rồi retry → reconciliation → status Admin.

Test bị skip nếu chưa đặt `PERSON_SEARCH_RUN_E2E=1`. Fixture `storage_stack` trong `conftest.py`
chạy `alembic downgrade base → upgrade head` nên DSN phải trỏ tới database dùng một lần. Mỗi lần
chạy dùng collection/alias Milvus riêng, camera UUID riêng và tự dọn object, collection, schema.

```sh
sh scripts/storage.sh up
cd backend
PERSON_SEARCH_RUN_E2E=1 .venv/bin/python -m pytest -m e2e -v
```

DSN phải trỏ tới database có tên kết thúc bằng `_test`/`_citest`, nếu không `tests/conftest.py` dừng ngay (exit 4). Trên Windows tạo bằng `.\scripts\test-db.ps1 create` rồi export DSN được in ra; xem `tests/integration/README.md`.

Khi một bước lỗi, thông báo có dạng `[minio] E2E step '...' failed: ...` để chỉ rõ component.
MinIO unavailable dùng endpoint thật không tồn tại (`127.0.0.1:1`); Milvus unavailable dùng client
giả ném `MilvusException` vì `MilvusClient` kết nối ngay khi khởi tạo.
