# Database migrations

Thư mục dành cho Alembic migrations của PostgreSQL.

Ở task `STO-00` chưa có SQLAlchemy model, Alembic environment hoặc migration revision.
Các thành phần đó được thêm từ `STO-04` và được kiểm tra đầy đủ ở `STO-07`.

Không đặt migration thủ công hoặc schema SQL tạm thời tại đây trước khi hợp đồng dữ liệu
được chốt ở `STO-01`.
