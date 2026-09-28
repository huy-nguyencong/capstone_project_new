# H2 — Kiến trúc tổng thể của hệ thống

- **Vị trí:** Mục 5.1 (Thiết kế kiến trúc hệ thống).
- **Chú thích hình (caption):** "Kiến trúc tổng thể của hệ thống".
- **Tệp:** `H2-kien-truc.drawio`, `H2-kien-truc.png`.
- **Loại sơ đồ:** sơ đồ kiến trúc → dùng bộ ký hiệu mục 3 trong `figures/README.md`.
- **Mục đích:** cho người đọc thấy các thành phần chính, tiến trình nào chạy riêng, dữ liệu nằm ở đâu, và hai luồng chính: (1) lập chỉ mục từ camera; (2) tìm kiếm của người dùng.

## 1. Bố cục tổng thể

> **Cập nhật 2026-09-28:** tệp `.drawio` được sinh bằng `report/tools/h2_architecture_drawio.py`. Bố cục đổi từ 4 cột ngang sang **2 cột dọc** để chữ in ra đạt ~9pt ở khổ 16 cm (chữ 20 px, hình rộng ~1.020 px). Các thay đổi so với bảng khối/mũi tên bên dưới: (1) khung nét đứt "Máy chủ ứng dụng" được gộp vào chính container C1 "Máy chủ ứng dụng (Flask API)" (container đã là ranh giới tiến trình); (2) A4 "Tệp video tải lên" đặt trong khung **Người dùng** (Quản trị viên tải tệp qua trình duyệt); (3) các mũi tên từ B8 vào ba kho **không có nhãn** (chú thích trong từng kho đã nói kho lưu gì); C1↔S1 và C2↔S2 dùng mũi tên hai đầu; S3→C1 "khung hình" thay cho C1→S3; (4) bỏ nhãn "luồng RTSP" trên đoạn dọc (nét đậm + chú giải đã thể hiện); (5) chú giải gồm tệp dữ liệu, xử lý, thành phần phần mềm, mô hình AI, CSDL, hàng đợi, kho đối tượng, camera, ba kiểu đường. Biểu tượng bộ não/camera/bucket là SVG nhúng trong tệp (draw.io offline không có sẵn).

| Vùng | Khung | Nội dung |
| --- | --- | --- |
| Trái, trên | **Nguồn dữ liệu camera** (nét đứt) | A1 → A2 → A3 |
| Trái, dưới | **Tiến trình xử lý nền (AI worker)** (nét đứt) | B1, B2 ở hàng đầu; B3 → B8 xếp dọc |
| Phải, trên | **Người dùng** (nét đứt) | 3 tác nhân, D1, A4 |
| Phải, dưới | container **Máy chủ ứng dụng (Flask API)** | C3, C2 |
| Dưới cùng | **Tầng lưu trữ** (nét đứt) | S1, S2, S3 |

Luồng lập chỉ mục: cột trái từ trên xuống rồi xuống tầng lưu trữ. Luồng tìm kiếm (màu xanh): cột phải từ trên xuống, xuống tầng lưu trữ và quay lại.

## 2. Bảng khối

| ID | Nhãn hiển thị | Hình (theo README mục 3) | Khung chứa | Ghi chú nội dung |
| --- | --- | --- | --- | --- |
| A1 | Tệp video WILDTRACK (7 camera) | Tài liệu nhiều trang (`Multi-Document`) | A | Nguồn dữ liệu giả lập |
| A2 | FFmpeg + MediaMTX | Chữ nhật bo góc (xử lý) | A | Dòng phụ nhỏ: "phát tệp video thành luồng RTSP" |
| A3 | 7 camera logic | Biểu tượng camera (vẽ 1 camera, ghi "×7") | A | Mỗi camera thuộc một khu vực |
| A4 | Tệp video tải lên (dự phòng) | Tài liệu | A | Đặt dưới A3, nhỏ hơn |
| B1 | Bộ lập lịch phiên RTSP | Chữ nhật bo góc | B | Dòng phụ: "xoay vòng camera, 1.800 khung/phiên" |
| B2 | Hàng đợi công việc | Trụ nằm ngang | B | Thực tế lưu trong PostgreSQL; ghi dòng phụ "(bảng processing_job)" |
| B3 | Lấy mẫu khung hình (1/N) | Chữ nhật bo góc | B | |
| B4 | Phát hiện người — YOLO11n | **Bộ não** | B | |
| B5 | Theo vết — ByteTrack / BoT-SORT | **Bộ não** | B | |
| B6 | Chọn khung hình đại diện | Chữ nhật bo góc | B | |
| B7 | Mã hóa ảnh — RaSa Image Encoder | **Bộ não** | B | |
| B8 | Ghi dữ liệu track | Chữ nhật bo góc | B | Dòng phụ: "PENDING → READY" |
| C1 | Flask API | Container (thanh tiêu đề) | C | Dòng phụ: "xác thực, phân quyền, tìm kiếm, vụ việc, quản trị" |
| C2 | Mã hóa truy vấn — RaSa Image/Text Encoder | **Bộ não** | Bên trong C1 hoặc sát cạnh C1 | Cùng checkpoint với B7 |
| C3 | Bộ tạo câu mô tả từ thuộc tính | Chữ nhật bo góc | Bên trong C1 | |
| D1 | Ứng dụng web (React) | Biểu tượng trình duyệt / màn hình | D | |
| D2 | Quản trị viên / Giám sát viên / Quản lý | 3 hình người đặt cạnh D1 | D | Chỉ dùng từ chương 4 trở đi nên hợp ở H2 |
| S1 | PostgreSQL | **Trụ** | Tầng lưu trữ | Dòng phụ: "tài khoản, camera, track, vụ việc, nhật ký" |
| S2 | Milvus | **Trụ**, ghi "vector" | Tầng lưu trữ | Dòng phụ: "vector 256 chiều + khu vực, camera, thời gian" |
| S3 | MinIO | **Xô (bucket)** | Tầng lưu trữ | Dòng phụ: "khung hình đại diện (bucket riêng tư)" |

## 3. Bảng mũi tên

| Từ | Đến | Nhãn | Kiểu |
| --- | --- | --- | --- |
| A1 | A2 | tệp video | Liền |
| A2 | A3 | luồng RTSP | **Đậm/nét đôi** |
| A3 | B3 | luồng RTSP | **Đậm/nét đôi** |
| A4 | C1 | tải lên | Liền |
| C1 | B2 | tạo công việc (tệp tải lên) | **Nét đứt** |
| B1 | B2 | tạo phiên RTSP | **Nét đứt** |
| B2 | B3 | công việc kế tiếp | **Nét đứt** |
| B3 | B4 | khung hình đã lấy mẫu | Liền |
| B4 | B5 | khung bao người | Liền |
| B5 | B6 | track đã kết thúc | Liền |
| B6 | B7 | ảnh người (cắt tạm) | Liền |
| B7 | B8 | vector đặc trưng | Liền |
| B8 | S1 | metadata track | Liền |
| B8 | S3 | khung hình đại diện | Liền |
| B8 | S2 | vector + trường lọc | Liền |
| D1 | C1 | ảnh / câu mô tả / thuộc tính | Liền |
| C1 | C3 | thuộc tính | Liền |
| C3 | C2 | câu mô tả tiếng Anh | Liền |
| C1 | C2 | ảnh / câu mô tả | Liền |
| C2 | S2 | vector truy vấn + điều kiện lọc | Liền |
| S2 | C1 | danh sách track + điểm | Liền |
| C1 | S1 | kiểm tra quyền, lấy metadata | Liền (hai chiều) |
| C1 | S3 | đọc khung hình | Liền |
| C1 | D1 | kết quả + ảnh cắt động | Liền |

Mẹo để tránh rối: đánh số tròn ①②③… trên các mũi tên của luồng tìm kiếm, và dùng một màu mũi tên khác (ví dụ xanh dương đậm) cho luồng tìm kiếm, màu đen cho luồng lập chỉ mục. Ghi hai màu này vào chú giải.

## 4. Chú giải (góc dưới phải)

Chỉ gồm các ký hiệu có trong hình: tài liệu (tệp dữ liệu), bình hành (nếu có dùng), chữ nhật bo góc (xử lý), container (thành phần phần mềm), bộ não (mô hình AI), trụ (cơ sở dữ liệu), xô (kho đối tượng), trụ nằm ngang (hàng đợi), camera, mũi tên đậm (luồng RTSP), mũi tên nét đứt (điều khiển), hai màu mũi tên (lập chỉ mục / tìm kiếm).

## 5. Điểm cần đối chiếu khi rà soát

- Worker và API là **hai tiến trình riêng**: B và C phải ở hai khung khác nhau.
- Bộ mã hóa truy vấn (C2) chạy **trong tiến trình API** (`InProcessQueryEncoder`), không nằm trong worker.
- Hàng đợi công việc thực chất là bảng trong PostgreSQL. Có thể vẽ riêng cho dễ hiểu nhưng phải có dòng phụ ghi chú.
- Trình duyệt **không** truy cập trực tiếp MinIO: mọi ảnh đi qua Flask API.
- Không vẽ etcd hay MinIO nội bộ của Milvus; các thành phần hạ tầng này để dành cho sơ đồ triển khai H9.
