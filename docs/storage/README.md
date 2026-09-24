# Storage architecture notes

Tài liệu trong thư mục này mô tả thiết kế và vận hành tầng lưu trữ của ứng dụng.

## Ranh giới thành phần

- `person_search.domain`: quy tắc và kiểu dữ liệu không phụ thuộc framework/storage.
- `person_search.services`: điều phối use case và transaction boundary.
- `person_search.storage.postgres`: metadata nghiệp vụ và repository quan hệ.
- `person_search.storage.milvus`: vector embedding và tìm kiếm có filter.
- `person_search.storage.minio`: full frame đại diện trong bucket private.
- `backend/migrations`: Alembic revisions của PostgreSQL.
- `infra`: dịch vụ local dùng cho integration test và demo.

## Trạng thái STO-00

Chỉ có package namespace và tooling. Chưa có client, model, migration, connection string,
bucket hoặc collection thật. Vì vậy import package và tạo Flask app không cần dịch vụ ngoài.

Các quyết định ID, timestamp, bounding box, state machine và naming được khóa ở `STO-01`.
