# Local infrastructure

Thư mục này chứa hạ tầng phát triển của ứng dụng.

Docker Compose cho PostgreSQL, Milvus Standalone và MinIO sẽ được thêm ở `STO-02`. Task
`STO-00` chỉ tạo ranh giới thư mục; chưa khai báo service hoặc credential giả định.

Nguyên tắc cho các task sau:

- Pin phiên bản image, không dùng `latest`.
- Không commit secret hoặc volume runtime.
- Có health check cho từng service.
- MinIO bucket chứa full frame phải private.
- Dữ liệu Milvus và object của ứng dụng phải có namespace/bucket tách biệt.
