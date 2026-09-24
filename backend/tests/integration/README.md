# Integration tests

Các test trong thư mục này sử dụng PostgreSQL, Milvus hoặc MinIO thật từ Docker Compose.
Chúng được đánh dấu `pytest.mark.integration` và không chạy trong bộ unit test nhanh.

Hạ tầng integration test được dựng ở `STO-02`; `STO-03` bổ sung smoke test kết nối thật cho
PostgreSQL, Milvus và MinIO. Test chỉ chạy khi đặt `PERSON_SEARCH_RUN_INTEGRATION=1` và đã export
các biến storage trong `backend/.env.example`.
