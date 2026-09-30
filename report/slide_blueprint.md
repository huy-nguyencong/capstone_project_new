# Blueprint nội dung và bố cục slide bảo vệ PRISM

> Hướng dẫn để tự thiết kế trên Canva. Không phải lời thuyết trình hoặc file slide hoàn chỉnh.  
> Giả định: 12–15 phút, 16 slide chính và phụ lục hỏi đáp.

## 1. Định hướng chung

- Khổ 16:9, nền xanh đen/tím than, chữ sáng; tím cho AI, cyan cho dữ liệu, cam cho hạn chế.
- Font Be Vietnam Pro, Inter hoặc Montserrat. Tiêu đề 30–34 pt; nội dung 18–24 pt; chú thích tối thiểu 12–14 pt.
- Mỗi slide chỉ có một ý chính và khoảng 25–45 từ. Ưu tiên sơ đồ, screenshot và số liệu.
- Không tóm tắt tuần tự 9 chương. Mạch chính: bài toán → giải pháp → kiến trúc → sản phẩm → kiểm thử → kết quả → hạn chế.
- Không thu nhỏ sơ đồ dọc nhiều chữ vào một góc slide ngang. Hãy vẽ lại bản rút gọn hoặc dùng ở phụ lục.

## 2. Các hình hiện có trong `report/thesis/figures/`

### Sơ đồ kỹ thuật

| File | Nội dung | Khuyến nghị |
| --- | --- | --- |
| `H1-use-case.png` | 15 use case, 3 vai trò | Chỉ dùng phụ lục; quá dày cho phần chính. |
| `H2-kien-truc.png` | Kiến trúc đầy đủ: nguồn camera, worker, API, ba kho | Là nguồn cho slide kiến trúc; nên vẽ lại bản ngang rút gọn. |
| `H3-luu-do-xu-ly-camera.png` | Lưu đồ xử lý một công việc camera | Có thể cắt sát và dùng; tốt nhất rút còn pipeline 6 bước. |
| `H4-tuan-tu-tim-kiem.png` | Sequence tìm kiếm | Dùng làm nguồn vẽ sequence ngắn; bản đầy đủ để phụ lục. |
| `H5-tuan-tu-vu-viec.png` | Sequence lưu vụ việc | Dùng làm nguồn kiểm tra; bản đầy đủ để phụ lục. |
| `H6-trang-thai-lan-xuat-hien.png` | `PENDING`, `READY`, `FAILED` | Có thể dùng gần nguyên bản ở phụ lục nhất quán ba kho. |
| `H7-trang-thai-cong-viec.png` | Vòng đời processing job | Phụ lục về worker, retry và hủy công việc. |
| `H8-erd.png` | ERD 11 bảng | Chỉ dùng phụ lục; có thể cắt riêng 6 bảng lõi. |
| `H12-luong-man-hinh.png` | Luồng màn hình theo vai trò | Có thể dùng gần nguyên bản ở phụ lục hoặc slide phạm vi sản phẩm. |

Các file `.drawio` tương ứng đều có sẵn. Khi cần bản ít chữ hơn, hãy sao chép file `.drawio` và tạo phiên bản riêng cho slide.

### Ảnh giao diện

- `H10a-tim-kiem-anh-cat.png`: ảnh tốt nhất để giới thiệu tìm kiếm và danh sách kết quả.
- `H10b-tim-kiem-thuoc-tinh-cat.png`: dùng minh họa phương thức thuộc tính.
- `H10c-chi-tiet-ket-qua-cat.png`: full frame, bbox, điểm, camera, khu vực và thời gian; rất phù hợp để giải thích đánh giá bằng ngữ cảnh.
- `H10d-tao-vu-viec-cat.png`: hộp thoại tạo vụ việc; ảnh dọc, chỉ nên làm hình phụ.
- `H10e-vu-viec-cua-toi-cat.png`: danh sách/chi tiết vụ việc của Giám sát viên.
- `H10f-tong-quan-cat.png`: dashboard Quản lý; ảnh rất rộng, nên đặt ngang hoặc cắt thành hai vùng.
- `H10g-camera-cat.png`: quản lý camera.
- `H10h-mo-hinh-ai-cat.png`: cấu hình Detector/Tracker.
- `H10i-xu-ly-video-cat.png`: công việc xử lý video.
- `H10j-trang-thai-he-thong-cat.png`: trạng thái hệ thống.
- `H10k-kiem-tra-ai-cat.png`: chẩn đoán AI.
- `briefcam.png`, `avigilon.png`, `verkada.png`: chỉ dùng nếu cần phụ lục về hệ thống liên quan.

## 3. Cấu trúc bài trình bày theo báo cáo

| Phần | Slide | Nội dung |
| --- | ---: | --- |
| Tổng quan đề tài | 2–3 | Bài toán, mục tiêu và phạm vi |
| Các hệ thống liên quan và cơ sở lý thuyết | 4–5 | Hệ thống liên quan, chuỗi kỹ thuật và ba phương thức truy vấn |
| Phân tích hệ thống | 6–7 | Tác nhân, chức năng, phân quyền và quy tắc nghiệp vụ |
| Thiết kế hệ thống | 8–10 | Kiến trúc, pipeline, luồng tìm kiếm và vụ việc |
| Hiện thực hệ thống | 11–12 | Công nghệ, lưu trữ và giao diện đã hiện thực |
| Thử nghiệm và đánh giá | 13–15 | Kiểm thử, chất lượng tìm kiếm, hiệu năng và dữ liệu demo |
| Tổng kết và định hướng phát triển | 16 | Kết quả đạt được, hạn chế và hướng phát triển |

Không cần tạo bảy slide phân cách chương riêng vì sẽ làm loãng bài trình bày. Thay vào đó, đặt tên phần nhỏ phía trên tiêu đề hoặc dùng màu nhận diện nhẹ cho từng nhóm slide.

## 4. Blueprint 16 slide chính

### Slide 1 — Trang bìa

**Nội dung:** tên đề tài, PRISM, sinh viên, MSSV, GVHD, Hội đồng, tháng bảo vệ.

**Bố cục:** chữ bên trái 55%, ảnh bên phải 45%. Dùng một vùng full frame có bbox từ `H10c`, không dùng sơ đồ.

### Slide 2 — Bài toán thực tế

**Nội dung:** nhiều camera tạo lượng video lớn; người tìm kiếm thường chỉ có ảnh hoặc đặc điểm ngoại hình; xem thủ công khó xác định camera và thời điểm xuất hiện.

**Bố cục:** full frame WILDTRACK chiếm 65%, đánh dấu một người; ba ý ngắn ở bên phải. Có thể cắt vùng ảnh từ `H10c`.

### Slide 3 — Mục tiêu và phạm vi

**Nội dung:** xây dựng ứng dụng lập chỉ mục người theo track và tìm bằng ảnh, văn bản, thuộc tính. Phạm vi: chỉ tìm người; truy vấn tiếng Anh; 7 RTSP giả lập; xử lý tuần tự; dùng mô hình có sẵn.

**Bố cục:** mục tiêu lớn ở trên; dưới là luồng camera → lập chỉ mục → tìm kiếm → vụ việc. Không cần hình báo cáo.

### Slide 4 — Hệ thống liên quan và nền tảng lý thuyết

**Nội dung:** nêu ngắn ba hướng tiếp cận đã khảo sát: BriefCam hỗ trợ tìm ngoại hình tương tự và Video Synopsis; Avigilon Appearance Search dùng thuộc tính và ví dụ từ ảnh/video; Verkada AI-Powered Search hỗ trợ câu truy vấn tự nhiên. Phần lý thuyết chỉ cần một chuỗi: phát hiện người → theo vết đa đối tượng → biểu diễn ảnh–văn bản → tìm kiếm vector.

**Bố cục:** nửa trái đặt ba ảnh `briefcam.png`, `avigilon.png`, `verkada.png` theo hàng dọc hoặc ba dải nhỏ; nửa phải là chuỗi bốn khái niệm lý thuyết. Dòng kết luận ở cuối: PRISM kết hợp truy vấn đa phương thức, phân quyền theo khu vực và hồ sơ vụ việc trong một ứng dụng triển khai tại chỗ. Không trình bày bảng so sánh dài.

### Slide 5 — Ba phương thức tìm kiếm

**Nội dung:** ảnh dùng Image Encoder; văn bản tiếng Anh dùng Text Encoder; thuộc tính sinh câu tiếng Anh rồi dùng Text Encoder; cùng so khớp với embedding track của RaSa.

**Bố cục:** ba đầu vào bên trái hội tụ vào “RaSa, vector 256 chiều”, kết quả xếp hạng bên phải. Cắt vùng truy vấn từ `H10a`, vùng thuộc tính từ `H10b`, không đặt nguyên screenshot.

### Slide 6 — Phân tích tác nhân và chức năng

**Nội dung:** ba tác nhân Quản trị viên, Giám sát viên và Quản lý; nhóm chức năng chính của từng vai trò; tổng cộng 15 use case. Chỉ nêu chức năng ở mức yêu cầu, chưa nhắc React, Flask hoặc ba kho lưu trữ.

**Bố cục:** ba cột theo vai trò, mỗi cột có 2–3 nhóm chức năng. Dựa trên `H1-use-case.png` và `H12-luong-man-hinh.png`, nhưng không đặt nguyên H1 vì quá nhiều chữ.

### Slide 7 — Phân quyền và quy tắc nghiệp vụ

**Nội dung:** Giám sát viên có đúng một khu vực; tìm kiếm chỉ trên camera đang vận hành thuộc khu vực đó; vụ việc thuộc một Giám sát viên và không gắn với khu vực; vụ việc hoàn thành bị khóa; Matching Score không được lưu.

**Bố cục:** một sơ đồ quan hệ đơn giản ở trái và 4 quy tắc ở phải. Phần này trình bày hệ thống phải làm gì, chưa nói cách Flask/Milvus hiện thực việc kiểm tra quyền.

### Slide 8 — Kiến trúc hệ thống

**Nội dung:** React web, Flask API, AI worker, FFmpeg/MediaMTX, PostgreSQL, Milvus và MinIO. Nhấn mạnh API giữ nghiệp vụ/quyền, worker chạy AI, ba kho giữ ba loại dữ liệu.

**Bố cục:** nguồn camera bên trái; web và API bên phải; worker ở giữa; ba kho ở hàng dưới. Dựa trên `H2` nhưng vẽ lại bản ngang, bỏ hàng đợi, bộ lập lịch và các mũi tên phụ.

### Slide 9 — Pipeline xử lý camera

**Nội dung:** đọc nguồn → lấy 1/20 frame → YOLO11n → ByteTrack/BoT-SORT → chọn frame đại diện → RaSa và ghi ba kho. Ghi thêm: một kết quả là một track; lưu full frame + bbox; chỉ `READY` được tìm kiếm.

**Bố cục:** pipeline ngang sáu bước. Dựa trên `H3`; không đưa nhánh `i mod N` và retry chi tiết lên slide chính.

### Slide 10 — Thiết kế luồng tìm kiếm và vụ việc

**Nội dung:** chọn truy vấn, camera, thời gian và `top_k ∈ {4,8,12,16}`; lọc phạm vi trước xếp hạng; crop động trong danh sách; full frame khi xem chi tiết; Matching Score không kết luận danh tính và không được lưu.

**Bố cục:** nửa trên là sequence tìm kiếm rút gọn dựa trên `H4`; nửa dưới là luồng Kết quả → Vụ việc đang xử lý → Hoàn thành dựa trên `H5`. Không dùng screenshot ở slide thiết kế.

### Slide 11 — Công nghệ và hiện thực lưu trữ

**Nội dung:** React + Vite cho giao diện; Flask API cho nghiệp vụ; Python worker cho AI; YOLO11n, ByteTrack/BoT-SORT và RaSa; PostgreSQL, Milvus và MinIO. Nêu `track_id` liên kết ba kho và trạng thái `PENDING → READY` bảo đảm dữ liệu chỉ được tìm kiếm khi ghi hoàn tất.

**Bố cục:** bảng hoặc sơ đồ hai tầng “thành phần” và “trách nhiệm”. Có thể dùng một vùng rút gọn từ `H2` và sơ đồ `H6` nhỏ ở góc, nhưng không lặp lại toàn bộ kiến trúc Slide 8.

### Slide 12 — Sản phẩm đã hiện thực

**Nội dung:** chỉ bốn nhãn: tìm kiếm và xếp hạng; đánh giá full frame; quản lý vụ việc; dashboard toàn hệ thống.

**Bố cục:** `H10a` làm ảnh lớn 60%; ba ảnh nhỏ bên phải: `H10c`, `H10e`, `H10f`. Không dùng cả 11 screenshot.

### Slide 13 — Kiểm thử hệ thống

**Nội dung:** 711 unit; 37 integration đạt và 1 bỏ qua; 2 E2E trong 217 giây; 20 màn hình × 3 kích thước; 2 kịch bản demo đạt 15/15 bước. Nhắc ngắn phân quyền, CSRF, rate limit và responsive 390 px.

**Bố cục:** bốn cụm số lớn theo hàng ngang; không dùng biểu đồ tròn và không cần screenshot.

### Slide 14 — Chất lượng tìm kiếm

**Nội dung:** lần đo 1, ảnh→ảnh Recall@4 = 0,83 và Recall@8–16 = 1,00; văn bản và thuộc tính Recall@4–16 = 0. Lần đo 2 chỉ đo lại thuộc tính với điều kiện khác và vẫn bằng 0. Kết luận: tìm bằng ảnh đáng tin cậy nhất trong thí nghiệm hiện có.

**Bố cục:** biểu đồ Recall@k bên trái, kết luận và nguyên nhân khác biệt miền CUHK-PEDES/WILDTRACK bên phải. Chú thích điều kiện: lần 1 ngưỡng 0,25, 1.552 track; lần 2 ngưỡng 0,1, 1.526 track. Không trộn hai lần thành cùng một chuỗi.

### Slide 15 — Hiệu năng và dữ liệu demo

**Nội dung:** i5-11300H, RAM 16 GB, không GPU rời; 7 camera; 1.488 track demo; 1.523 track toàn hệ thống; xử lý 1080p60 chậm hơn thời gian thực khoảng 7 lần; lần tìm đầu khoảng 30 giây, sau đó khoảng 8 giây trong kịch bản đã ghi nhận.

**Bố cục:** ba số lớn `7 camera`, `1.523 track`, `≈7×`; thông tin máy và độ trễ ở hai chú thích riêng. Không đưa RAM toàn stack hoặc p50/p95 vì chưa đo chính thức.

### Slide 16 — Tổng kết và định hướng phát triển

**Nội dung:** bên trái tóm tắt kết quả: hoàn thiện pipeline camera–track; ba cách truy vấn; quyền theo vai trò/khu vực; luồng vụ việc và dashboard; kiểm thử và đánh giá trên WILDTRACK. Bên phải ghép hạn chế với hướng phát triển: Recall text thấp → reranking/fine-tune cùng miền; CPU chậm → OpenVINO/GPU; timestamp RTSP → timestamp luồng; một frame/track → nhiều frame; ghi theo phiên → ghi khi track kết thúc; chưa cross-camera → liên kết xuyên camera.

**Bố cục:** chia 45/55. Cột trái là 4–5 kết quả đạt được; cột phải là ba cặp hạn chế và hướng phát triển quan trọng nhất. Không dùng screenshot để tránh làm loãng slide kết luận.

## 5. Phụ lục hỏi đáp

- **Use case:** `H1-use-case.png` toàn màn hình.
- **Luồng màn hình:** `H12-luong-man-hinh.png`.
- **ERD:** `H8-erd.png`; nên có thêm bản cắt 6 bảng lõi.
- **Nhất quán ba kho:** `H6-trang-thai-lan-xuat-hien.png`, thêm câu “chỉ READY được tìm kiếm”.
- **Processing job:** `H7-trang-thai-cong-viec.png`.
- **Sequence tìm kiếm:** `H4-tuan-tu-tim-kiem.png`.
- **Sequence vụ việc:** `H5-tuan-tu-vu-viec.png`.
- **Chức năng Admin:** bố cục 2×2 với `H10g`, `H10h`, `H10j`, `H10k`; `H10i` có thể để riêng.
- **Hệ thống liên quan:** `briefcam.png`, `avigilon.png`, `verkada.png` nếu bị hỏi về sản phẩm tương tự.

## 6. Quy tắc xử lý hình trong Canva

- Giữ đúng tỉ lệ, cắt sát khoảng trắng, không kéo méo.
- H2/H3/H4/H5 nên vẽ lại bản rút gọn; H6/H7/H12 có thể dùng gần nguyên bản; H1/H8 chỉ để phụ lục.
- Screenshot dùng viền mảnh hoặc bóng nhẹ; không thêm khung trình duyệt giả.
- Muốn nhấn một vùng, phủ tối 25–35% phần còn lại thay vì khoanh nhiều vòng.
- `H10d` là ảnh dọc nên chỉ làm hình phụ. `H10f` rất rộng nên đặt ngang hoặc cắt thành hai vùng.
- Biểu đồ Recall dựng trực tiếp trong Canva, trục tung 0–1, không dùng 3D, ghi điều kiện đo ngay dưới biểu đồ.

## 7. Các phát biểu cần tránh

- Không gọi hệ thống là nhận diện danh tính hoặc nhận diện khuôn mặt.
- Không nói đã huấn luyện/tinh chỉnh AI hoặc xử lý đồng thời 7 camera.
- Không nói thuộc tính là mô hình riêng, hỗ trợ tiếng Việt hoặc tự động dịch.
- Không nói Matching Score được lưu trong vụ việc hay person crop được lưu độc lập.
- Không nói camera ngừng vận hành làm mất lịch sử.
- Không khẳng định text/thuộc tính có chất lượng tốt.
- Không dùng số RAM, p50/p95 hoặc độ chính xác chưa đo; không gọi tốc độ hiện tại là thời gian thực.

## 8. Checklist trước khi làm Canva

- [ ] Xác nhận thời lượng chính thức.
- [ ] Chọn palette và một font duy nhất.
- [ ] Tạo bản ngang rút gọn từ H2 và H3.
- [ ] Cắt các vùng cần dùng từ H10a, H10b, H10c, H10e và H10f.
- [ ] Dựng biểu đồ Recall@k và ghi đủ điều kiện đo.
- [ ] Đối chiếu mọi số với `files/report-data-guide.md`.
- [ ] Kiểm tra chữ trên sơ đồ đọc được khi trình chiếu toàn màn hình.
- [ ] Đưa H1, H4, H5, H6, H7 và H8 vào phụ lục.
- [ ] Xuất cả PDF và PPTX từ Canva để dự phòng.
