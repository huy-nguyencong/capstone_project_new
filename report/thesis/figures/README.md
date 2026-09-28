# Sơ đồ trong báo cáo — quy ước và quy trình

**Quy trình (từ 2026-09-28):** Claude dựng sẵn tệp `.drawio` bằng đúng các hình có sẵn của draw.io, đặt vị trí tay theo đặc tả; sinh viên mở tệp, chỉnh lại theo tay mình rồi xuất ảnh. Claude **không** dùng Mermaid, PlantUML, Graphviz hay ảnh sinh tự động (bố cục máy móc, trông thiếu tự nhiên). Ảnh chụp màn hình ứng dụng do sinh viên tự chụp.

## 1. Quy trình cho mỗi sơ đồ

1. Claude viết `specs/H<mã>-<tên>.md`: mục đích, danh sách khối, danh sách mũi tên, bố cục, chú giải, điểm cần đối chiếu với code.
2. Claude tạo `H<mã>-<tên>.drawio` trong thư mục này theo đặc tả, dùng bộ ký hiệu ở mục 2–3.
   Trước khi giao, Claude xuất ảnh xem trước bằng draw.io desktop đã cài trên máy (bản Microsoft Store, lệnh `draw.io.exe -x -f png -s 1 -b 10 -o <ảnh> <tệp.drawio>` trong thư mục cài đặt của gói `draw.io.draw.ioDiagrams`) để tự kiểm tra các đường nối cắt nhau, chữ bị đè, khoảng trống thừa, rồi chỉnh tọa độ.
3. Sinh viên mở tệp trên draw.io (app.diagrams.net hoặc bản desktop) và chỉnh theo tay: vị trí, khoảng cách, độ cong đường nối, font, màu trong bảng màu mục 3. Có thể thêm/bớt chi tiết trình bày, nhưng giữ đủ nội dung theo mục "Điểm cần đối chiếu" của đặc tả.
4. Sinh viên xuất **ảnh** `H<mã>-<tên>.png` (mục 4) vào thư mục này và lưu lại tệp `.drawio` đã chỉnh.
5. Claude đối chiếu ảnh với đặc tả và code, góp ý nếu cần.
6. Khi ảnh đạt, Claude thay khung giữ chỗ `\hinhcho{...}` trong báo cáo bằng `\includegraphics` và cập nhật trạng thái trong `report_plan.md` mục 7.

## 2. Hai loại sơ đồ — hai cách ký hiệu

| Loại sơ đồ | Ví dụ trong báo cáo | Ký hiệu dùng |
| --- | --- | --- |
| **Sơ đồ UML** | Use case (H1), sequence (H4, H5), trạng thái (H6, H7) | **Ký hiệu UML chuẩn** (actor hình người, use case hình elip, lifeline, trạng thái bo góc…). Không thay bằng biểu tượng tự chọn, vì hội đồng chấm theo chuẩn UML. |
| **ERD** | H8 | Ký hiệu **Crow's foot** chuẩn. |
| **Sơ đồ khối / luồng xử lý / kiến trúc / triển khai** | Kiến trúc (H2), pipeline camera (H3), triển khai (H9) | **Bộ ký hiệu riêng ở mục 3** theo yêu cầu của thầy: dữ liệu, xử lý, kho, AI… mỗi loại một hình. |

## 3. Bộ ký hiệu cho sơ đồ khối, luồng xử lý, kiến trúc

Dùng **thống nhất trong mọi sơ đồ**. Mỗi sơ đồ có một ô **chú giải** nhỏ ở góc, chỉ liệt kê các ký hiệu có mặt trong sơ đồ đó.

| Ý nghĩa | Hình vẽ | Trong draw.io (thanh tìm kiếm hình) | Màu nền gợi ý |
| --- | --- | --- | --- |
| Người dùng / vai trò | Hình người | `actor` (UML) hoặc `user` | Không màu |
| Dữ liệu đầu vào / đầu ra (ảnh, câu mô tả, kết quả) | **Hình bình hành** | Flowchart → `Data` | Vàng nhạt `#FFF2CC` |
| Tệp dữ liệu (video, tệp tải lên) | **Hình tài liệu** (đáy lượn sóng) | Flowchart → `Document` / `Multi-Document` | Vàng nhạt `#FFF2CC` |
| Bước xử lý / quá trình | **Hình chữ nhật bo góc** | General → `Rounded Rectangle` | Xanh dương nhạt `#DAE8FC` |
| Thành phần phần mềm lớn (API, worker, giao diện web) | **Hình chữ nhật có thanh tiêu đề** (container) hoặc biểu tượng máy chủ | Container/`Swimlane`, hoặc `server` | Xanh lá nhạt `#D5E8D4` |
| Mô hình AI (Detector, Tracker, Encoder) | **Biểu tượng bộ não** kèm nhãn | Tìm `brain`; hoặc Canva → Elements → "brain icon" | Tím nhạt `#E1D5E7` |
| Cơ sở dữ liệu quan hệ | **Hình trụ (cylinder)** | Flowchart → `Database` / `Cylinder` | Cam nhạt `#FFE6CC` |
| Cơ sở dữ liệu vector | Hình trụ, **ghi rõ "vector"** hoặc thêm biểu tượng mũi tên nhỏ | `Cylinder` | Cam nhạt, viền đậm hơn |
| Kho đối tượng (lưu ảnh) | **Hình xô/thùng (bucket)** hoặc thư mục | Tìm `bucket` hoặc `folder` | Cam nhạt `#FFE6CC` |
| Hàng đợi công việc | **Hình trụ nằm ngang** | `Cylinder` xoay 90° hoặc tìm `queue` | Cam nhạt |
| Camera | **Biểu tượng camera** | Tìm `camera` / `cctv` | Không màu |
| Luồng video (RTSP) | Mũi tên **nét đôi hoặc đậm** kèm nhãn "RTSP" | Connector, tăng độ dày | — |
| Quyết định / rẽ nhánh | **Hình thoi** | Flowchart → `Decision` | Trắng |
| Ranh giới (tiến trình, máy, mạng) | **Khung nét đứt** bao quanh nhóm | Rectangle, kiểu viền `dashed` | Không màu |

**Mũi tên:**
- **Nét liền, đầu tam giác đặc:** luồng dữ liệu chính (có nhãn nêu dữ liệu gì).
- **Nét đứt:** lời gọi điều khiển hoặc bất đồng bộ (ví dụ tạo công việc vào hàng đợi, đọc cấu hình).
- Mỗi mũi tên **có nhãn ngắn** (danh từ: "ảnh truy vấn", "vector 256 chiều", "full frame"…), tránh để mũi tên không nhãn.

## 4. Quy định trình bày chung

- **Font:** một font duy nhất trong mọi sơ đồ (gợi ý Arial hoặc Times New Roman), nhãn **tiếng Việt**; chỉ giữ tiếng Anh cho tên riêng (Flask, PostgreSQL, YOLO11n…).
- **Cỡ chữ:** khi chèn vào báo cáo rộng 16 cm, chữ nhỏ nhất vẫn phải đọc được, tương đương cỡ 9–10pt. Khung rộng khoảng 1.000–1.200 px thì chữ cần khoảng 22–24 px (14 px là quá nhỏ). Công thức kiểm tra: cỡ chữ in ra (pt) ≈ cỡ chữ (px) × 16 cm ÷ chiều rộng hình (px) × 28,35; cần đạt khoảng 9–10pt (ví dụ H1: chữ 24 px, hình rộng ~1.190 px → ~9pt).
- **Màu:** dùng đúng bảng màu ở mục 3, không tô màu tùy ý; in trắng đen vẫn phân biệt được nhờ **hình dạng** khác nhau.
- **Hướng đọc:** trái → phải hoặc trên → xuống; hạn chế mũi tên cắt nhau.
- **Xuất ảnh:** PNG, tỉ lệ 2× hoặc 300 dpi, nền trắng, có viền trống xung quanh (draw.io: File → Export as → PNG → Zoom 200%, Border 10). Luôn lưu kèm file `.drawio`.

## 5. Mẫu đặc tả

Mỗi file trong `specs/` theo mẫu: **Mục đích và vị trí trong báo cáo → Bố cục tổng thể → Bảng khối → Bảng mũi tên → Chú giải → Điểm cần đối chiếu.**
