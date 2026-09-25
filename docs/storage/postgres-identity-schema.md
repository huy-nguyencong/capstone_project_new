# PostgreSQL identity schema — STO-04

Migration `20260925_0001` tạo ba bảng nền `areas`, `users`, `cameras`. ID là UUIDv4 do
application tạo; database không sinh ID để cùng định danh có thể được dùng trước mọi I/O.

## Quy tắc được thực thi tại database

- `areas.code` và `cameras.code` unique, viết hoa và bất biến sau khi tạo.
- `users.role = OPERATOR` bắt buộc có đúng một `assigned_area_id` dạng scalar foreign key.
- `ADMIN` và `VIEWER` bắt buộc không có `assigned_area_id`.
- `cameras.area_id` bắt buộc, dùng `ON DELETE RESTRICT` và bất biến bằng trigger PostgreSQL.
- ORM cũng chặn đổi `Camera.area_id` trước flush để trả lỗi sớm; trigger vẫn là lớp bảo vệ cuối
  cho raw SQL hoặc client khác.
- User có trạng thái `ACTIVE`, `LOCKED`, `INACTIVE`, `DELETED`; Camera có `ACTIVE`, `INACTIVE`,
  `RETIRED`. Ngừng hoạt động không xóa row hoặc foreign key.
- `rtsp_url` được phép `NULL` cho luồng file video. Nếu có, URL phải dùng `rtsp://`/`rtsps://`
  và không được nhúng user/password; credential chỉ được tham chiếu qua `rtsp_secret_ref`.
- Trigger cập nhật `updated_at` áp dụng cả ORM lẫn raw SQL; timestamp dùng `timestamptz`.

## Ranh giới task

STO-04 chỉ định nghĩa schema và guard bất biến tối thiểu. Repository nghiệp vụ đầy đủ nằm ở
STO-08; bảng track/job và các foreign key lịch sử tương ứng được thêm ở STO-05/STO-06.
