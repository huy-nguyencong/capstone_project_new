# Integration tests

Các test trong thư mục này sử dụng PostgreSQL, Milvus hoặc MinIO thật từ Docker Compose.
Chúng được đánh dấu `pytest.mark.integration` và không chạy trong bộ unit test nhanh.

Hạ tầng integration test sẽ được bổ sung ở `STO-02` và kết nối ứng dụng ở `STO-03`.
