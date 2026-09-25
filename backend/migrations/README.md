# Database migrations

Alembic lấy URL PostgreSQL từ `PERSON_SEARCH_POSTGRES_DSN`. Từ thư mục `backend`:

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade base
```

Migration `20260925_0001` tạo Area/User/Camera, enum, constraint và trigger bất biến. Không chạy
downgrade trên database chứa dữ liệu cần giữ nếu chưa backup.

Migration `20260925_0002` tạo AI config, processing job, PersonTrack và transactional outbox;
đồng thời bảo vệ vòng đời `PENDING → READY/FAILED`, retry `FAILED → PENDING` và điều kiện
artifact bắt buộc trước khi track chuyển sang `READY`.
