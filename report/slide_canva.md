# Nội dung slide bảo vệ PRISM (19 slide, để dán vào Canva)

- **Hình:** sơ đồ và ảnh chụp màn hình nằm trong `report/thesis/figures/`; logo trường là `report/thesis/images/Logo_BK.png`.
- **Số liệu:** lấy từ Chương 7 và 8 của báo cáo. Số nào có điều kiện đo thì dòng chú thích ghi điều kiện đó ngay dưới số.
- **Quy ước chung:** khổ 16:9. Góc trên bên trái có nhãn phần nhỏ (ví dụ `TỔNG QUAN`), bên dưới là tiêu đề slide. Góc dưới bên phải ghi số trang.
- **Cách đọc tệp:** mỗi slide có ba phần là **Bố cục**, **Nội dung** (dán nguyên văn) và **Hình**.

---

## Slide 1 — Trang bìa

**Bố cục:** Dải trên cùng đặt logo bên trái, tên trường và khoa bên phải. Giữa slide là tên đề tài (chữ lớn nhất) và một dòng tên PRISM. Nửa dưới chia hai cột thông tin. Nếu muốn, đặt một ảnh mờ bên phải, lấy từ vùng khung hình toàn cảnh của H10c.

**Nội dung:**

> ĐẠI HỌC QUỐC GIA TP.HCM — TRƯỜNG ĐẠI HỌC BÁCH KHOA
> KHOA KHOA HỌC VÀ KỸ THUẬT MÁY TÍNH
>
> ĐỒ ÁN TỐT NGHIỆP
> **PHÁT TRIỂN HỆ THỐNG TÌM KIẾM NGƯỜI DỰA TRÊN MÔ TẢ ĐA PHƯƠNG THỨC**
> PRISM — Person Retrieval via Image & Semantic Matching
>
> GVHD: TS. Lê Thành Sách  |  GVPB: TS. Trần Tuấn Anh  |  Hội đồng: 1CC
> SVTH: Nguyễn Công Huy — 2113499
>
> TP. Hồ Chí Minh, tháng 10/2026

**Hình:** `images/Logo_BK.png`; tùy chọn thêm vùng cắt từ `figures/H10c-chi-tiet-ket-qua-cat.png`.

---

## Slide 2 — Bối cảnh và vấn đề

**Bố cục:** Cột trái (40%) gồm 2 số lớn xếp dọc, nguồn ghi chữ nhỏ bên dưới. Cột phải (60%) gồm 3 gạch đầu dòng về vấn đề, sau đó là một câu hỏi in đậm đặt trong khung màu nhấn.

**Nội dung, cột trái:**

> **> 20 triệu** camera giám sát đang sử dụng tại Việt Nam (ước tính năm 2025)
> **29% → 20% lên 50%**: hình ảnh camera hữu ích cho điều tra ở khoảng 29% số vụ; khi có hình ảnh hữu ích, tỉ lệ vụ việc được giải quyết tăng từ ~20% lên ~50%
>
> *Nguồn: VnExpress (26/08/2024); Ashby (2017), 251.195 vụ việc.*

**Nội dung, cột phải:**

> - Tìm một người = xem lại thủ công từng đoạn video của từng camera → tốn thời gian, dễ bỏ sót
> - Thông tin ban đầu thường chỉ là **một ảnh**, **một câu mô tả** hoặc **vài đặc điểm trang phục**
> - Nhiều người dùng, nhiều khu vực → cần phân quyền dữ liệu và lưu kết quả thành hồ sơ
>
> **Làm sao biết nhanh "người này xuất hiện ở camera nào, lúc nào?" từ nhiều dạng mô tả khác nhau?**

**Hình:** không bắt buộc. Nếu cần, dùng khung hình toàn cảnh cắt từ `H10c` làm nền mờ sau cột trái.

---

## Slide 3 — Mục tiêu, phạm vi và đóng góp

**Bố cục:** Dòng mục tiêu tổng quát chạy ngang phía trên. Giữa slide chia 3 cột bằng nhau: Mục tiêu, Phạm vi, Đóng góp. Dưới cùng là một dải sơ đồ 5 ô nối bằng mũi tên, vẽ trực tiếp trong Canva.

**Nội dung:**

> **Mục tiêu tổng quát:** Xây dựng ứng dụng hỗ trợ tìm người trong dữ liệu camera giám sát bằng nhiều hình thức mô tả. Hệ thống đề xuất và xếp hạng, người dùng ra quyết định.
>
> **Mục tiêu cụ thể**
> 1. Chuyển dữ liệu camera thành dữ liệu tìm kiếm được, theo từng lần xuất hiện
> 2. Tìm bằng ảnh, câu mô tả hoặc thuộc tính ngoại hình
> 3. Đánh giá kết quả trong khung hình gốc, lưu thành hồ sơ vụ việc
> 4. Phân quyền theo vai trò và khu vực giám sát
> 5. Đánh giá mô hình AI có sẵn trên phần cứng phổ thông
>
> **Phạm vi**
> - Chỉ tìm người; không nhận dạng khuôn mặt, không xác định danh tính
> - Truy vấn bằng tiếng Anh
> - 7 camera giả lập bằng luồng RTSP (bộ dữ liệu WILDTRACK)
> - Xử lý lần lượt từng camera
> - Dùng mô hình có sẵn, không huấn luyện
> - Một máy tính chỉ có CPU
>
> **Đóng góp**
> - Ứng dụng web hoàn chỉnh: camera → tìm kiếm → hồ sơ vụ việc
> - Ba hình thức truy vấn trên **cùng một không gian vector**
> - Lọc theo khu vực **trước** khi xếp hạng
> - Ghi dữ liệu nhất quán giữa ba kho
> - Số liệu thực nghiệm về chất lượng, tốc độ và bộ nhớ trên CPU
>
> *Dải sơ đồ:* Camera → Lập chỉ mục → Tìm kiếm → Đánh giá → Vụ việc

**Hình:** không dùng hình của báo cáo; tự vẽ dải 5 ô trong Canva.

---

## Slide 4 — Các hệ thống liên quan

**Bố cục:** 3 thẻ ngang bằng nhau, mỗi thẻ có ảnh ở trên (cao khoảng 45% thẻ) và 3 dòng mô tả bên dưới. Dưới cùng là một thẻ rộng màu nhấn nói về PRISM.

**Nội dung:**

> **BriefCam** (Milestone Systems)
> - Tìm theo thuộc tính; tìm ngoại hình tương tự từ mẫu chọn trong video
> - Tóm tắt video (Video Synopsis)
> - Máy chủ bắt buộc có GPU NVIDIA
>
> **Avigilon Appearance Search**
> - Tải ảnh lên hoặc chọn mẫu trong video
> - Mô tả bằng thuộc tính: màu quần áo, giới tính, nhóm tuổi
> - Cần camera/đầu ghi của hãng hoặc thiết bị AI Appliance
>
> **Verkada AI-Powered Search**
> - Tìm bằng câu mô tả tự do
> - Ảnh và câu truy vấn vào cùng không gian biểu diễn (CLIP) + CSDL vector
> - Chạy trên nền tảng đám mây của hãng
>
> **PRISM:** kết hợp **ảnh + câu mô tả + thuộc tính** trong một không gian biểu diễn; bổ sung **hồ sơ vụ việc** và **phân quyền theo khu vực**; triển khai **tại chỗ**, không cần GPU rời, nhận camera RTSP bất kỳ.

**Hình:** `figures/briefcam.png`, `figures/avigilon.png`, `figures/verkada.png`. Ảnh avigilon gần vuông; cắt cả 3 ảnh về cùng chiều cao.

---

## Slide 5 — Cơ sở lý thuyết và hướng tiếp cận

**Bố cục:** Nửa trên là chuỗi 4 ô ngang nối bằng mũi tên, mỗi ô gồm tên, mô hình và một dòng nguyên lý. Nửa dưới bên trái là sơ đồ "3 đầu vào hội tụ": Ảnh, Câu mô tả, Thuộc tính → câu, cùng đi vào ô RaSa, ra vector rồi tới so khớp. Nửa dưới bên phải là 2 ý về hướng tiếp cận.

**Nội dung, chuỗi 4 ô:**

> **① Phát hiện người · YOLO11n**: phát hiện một giai đoạn → khung bao + độ tin cậy, lọc trùng bằng NMS
> **② Theo vết · ByteTrack**: bộ lọc Kalman + thuật toán Hungary; liên kết thêm lần hai với phát hiện có độ tin cậy thấp → gom các khung hình thành một **track**
> **③ Biểu diễn ảnh–văn bản · RaSa**: ảnh và câu mô tả vào cùng không gian 256 chiều; chuẩn hóa L2 → tích vô hướng = độ tương đồng cosine
> **④ Tìm kiếm vector · HNSW (Milvus)**: tìm gần đúng trên đồ thị phân tầng; lọc camera/khu vực/thời gian trước khi lấy top-k
>
> *Trước ①: lấy mẫu 1 trong N khung hình (N = 20) để giảm số lần chạy mô hình.*

**Nội dung, hướng tiếp cận:**

> - **Hai bước:** phát hiện người trong khung hình → so khớp vùng người với truy vấn
> - **Lập chỉ mục trước, truy vấn sau:** video được phân tích một lần; mỗi truy vấn chỉ cần mã hóa rồi tìm vector, không xử lý lại video

**Hình:** tự vẽ trong Canva, không dùng hình của báo cáo.

---

## Slide 6 — Tác nhân và chức năng chính

**Bố cục:** Bên trái (45%) đặt H1 cao hết slide; ảnh dọc nên không kéo rộng. Bên phải (55%) là 3 thẻ vai trò xếp dọc, mỗi thẻ có một màu riêng. Dưới cùng bên phải là một dòng tổng kết.

**Nội dung:**

> **Quản trị viên (Admin)**: quản trị kỹ thuật
> Tài khoản và khu vực của Giám sát viên · Camera RTSP, bật/tắt xử lý AI · Chọn Detector/Tracker · Trạng thái hệ thống, kiểm tra AI, nhật ký
> *Không mặc định được tìm kiếm hay xem vụ việc*
>
> **Giám sát viên (Operator)**: nghiệp vụ chính
> Tìm người trong khu vực được giao · Đánh giá kết quả trên khung hình gốc · Tạo và quản lý vụ việc của mình
>
> **Quản lý (Viewer)**: theo dõi, chỉ đọc
> Trang tổng quan · Xem mọi vụ việc và kết quả đã lưu
>
> *15 use case · 3 tác nhân · đăng nhập/đăng xuất dùng chung*

**Hình:** `figures/H1-use-case.png` (2367×2837, ảnh dọc).

---

## Slide 7 — Các quy tắc nghiệp vụ quan trọng

**Bố cục:** Lưới 5 thẻ (3 thẻ hàng trên, 2 thẻ hàng dưới), mỗi thẻ có icon, tên quy tắc và 2 dòng nội dung. Dưới cùng là một câu chốt đặt giữa.

**Nội dung:**

> **Khu vực**: Camera thuộc đúng 1 khu vực, không đổi sau khi tạo. Giám sát viên được giao đúng 1 khu vực và chỉ tìm được trên camera **đang vận hành** của khu vực đó; máy chủ kiểm tra ở mọi yêu cầu.
>
> **Track (lần xuất hiện)**: Một kết quả = một lần xuất hiện của một người trên một camera, không phải một khung hình. Hệ thống lưu 1 khung hình toàn cảnh + khung bao + vector; ảnh người được cắt động khi hiển thị.
>
> **top-k**: Chỉ nhận 4, 8, 12 hoặc 16. Không dùng ngưỡng điểm để loại kết quả.
>
> **Vụ việc**: Có đúng một Giám sát viên phụ trách và không gắn với khu vực. Trạng thái **Đang xử lý ↔ Hoàn thành**; vụ việc hoàn thành bị khóa và mở lại được. Mỗi lần lưu tạo một mục mới.
>
> **Matching Score (Điểm phù hợp)**: Chỉ dùng để xếp hạng trong lượt tìm hiện tại. Không lưu vào vụ việc, không phải kết luận về danh tính.
>
> **Hệ thống đề xuất và xếp hạng — người dùng là người quyết định.**

**Hình:** chỉ dùng icon của Canva.

---

## Slide 8 — Kiến trúc tổng thể

**Bố cục:** Bên trái (50%) đặt H2 cao hết slide; ảnh dọc, không thu nhỏ vào góc. Bên phải là 5 khối chú giải xếp dọc, mỗi khối có màu trùng với vùng tương ứng trên hình. Dưới cùng là 2 nguyên tắc thiết kế.

**Nội dung:**

> **Nguồn camera**: FFmpeg + MediaMTX phát 7 video thành 7 luồng RTSP; tệp video tải lên là đường dự phòng
> **Tiến trình xử lý nền**: lấy mẫu → phát hiện → theo vết → mã hóa; xử lý 1 camera tại một thời điểm
> **Máy chủ ứng dụng (Flask)**: xác thực, phân quyền, tìm kiếm, vụ việc; mã hóa truy vấn
> **Ba kho dữ liệu**: PostgreSQL (nghiệp vụ, quyền, hàng đợi) · Milvus (vector) · MinIO (khung hình, bucket riêng tư)
> **Ứng dụng web (React)**: một giao diện cho 3 vai trò
>
> **Nguyên tắc:**
> ① Việc chậm (phân tích video) tách khỏi việc cần nhanh (API)
> ② Mọi ảnh đều đi qua bước kiểm tra quyền của máy chủ

**Hình:** `figures/H2-kien-truc.png` (2295×2735, ảnh dọc).

---

## Slide 9 — Luồng xử lý dữ liệu camera

**Bố cục:** Bên trái (55%) đặt H3. Bên phải là 3 khối: Tạo công việc, Giai đoạn 1, Giai đoạn 2. Dưới cùng là một dòng lưu ý màu cam.

**Nội dung:**

> **Tạo công việc**
> - Phiên RTSP tự động: chọn camera lâu nhất chưa được xử lý, mỗi phiên 1.800 khung (~30 giây video); camera lỗi được bỏ qua 5 phút
> - Hoặc tệp video do Quản trị viên tải lên
>
> **Giai đoạn 1: Vòng lặp khung hình**
> Đọc khung → lấy 1/20 → YOLO11n → ByteTrack → bộ đệm track
> Khi track kết thúc: chọn **khung hình đại diện** (giữ tối đa 3 ứng viên, chấm điểm chất lượng)
>
> **Giai đoạn 2: Mã hóa và ghi**
> Cắt tạm vùng người → RaSa → vector 256 chiều → ghi ba kho → **Sẵn sàng**
>
> *Dữ liệu chỉ tìm được sau khi công việc xử lý xong nguồn. Lỗi tạm thời được thử lại tối đa 3 lần.*

**Hình:** `figures/H3-luu-do-xu-ly-camera.png` (2289×1955). Nếu muốn, đặt thêm `H7-trang-thai-cong-viec.png` ở slide dự phòng.

---

## Slide 10 — Luồng tìm kiếm người

**Bố cục:** Bên trái (45%) đặt H4 cao hết slide; ảnh dọc. Bên phải là 4 bước đánh số và một khung kết quả ở cuối.

**Nội dung:**

> **1. Kiểm tra đầu vào**: ảnh JPEG/PNG ≤ 10 MB; thuộc tính hợp lệ; k ∈ {4, 8, 12, 16}
> **2. Xác định phạm vi**: khu vực lấy từ tài khoản đăng nhập, không lấy từ yêu cầu gửi lên; camera ngoài phạm vi bị từ chối
> **3. Mã hóa truy vấn**: ảnh → bộ mã hóa ảnh; câu mô tả → bộ mã hóa văn bản; thuộc tính → câu tiếng Anh theo mẫu
>   *"A woman wearing a red jacket and blue jeans, carrying a handbag."*
> **4. Tìm có lọc trước** trong Milvus → đối chiếu lại với PostgreSQL → nếu thiếu kết quả hợp lệ thì tìm lại với số lượng gấp đôi (tối đa 3 lượt)
>
> **Kết quả:** danh sách kèm Điểm phù hợp. Ảnh của từng kết quả được lấy bằng yêu cầu riêng; máy chủ kiểm tra quyền rồi cắt ảnh động từ khung hình toàn cảnh.

**Hình:** `figures/H4-tuan-tu-tim-kiem.png` (2059×2455, ảnh dọc).

---

## Slide 11 — Dữ liệu và tính nhất quán

**Bố cục:** Nửa trên bên trái (60%) đặt H6. Nửa trên bên phải là phần nêu vấn đề và 3 ràng buộc CSDL. Nửa dưới là dải 4 bước ghi nằm ngang, đánh số 1–4.

**Nội dung:**

> **Vấn đề:** một track được ghi vào 3 kho, nhưng 3 kho không có giao dịch chung.
>
> **Thứ tự ghi**
> ① PostgreSQL: bản ghi **Chờ** + sự kiện outbox (cùng một giao dịch)
> ② MinIO: khung hình
> ③ Milvus: vector, đọc lại để xác nhận
> ④ PostgreSQL: **Sẵn sàng**
>
> - Chỉ track **Sẵn sàng** mới được tìm kiếm
> - Lỗi tạm thời: thử lại (chờ 2 giây, tăng gấp đôi mỗi lần, tối đa 300 giây); sau 5 lần thì chuyển **Thất bại**
> - Có công cụ đối soát ba kho
>
> **CSDL quan hệ: 12 bảng, ràng buộc đặt ngay trong CSDL**
> - Không bảng nào lưu điểm phù hợp
> - Khu vực của camera không đổi được
> - Track chỉ ở trạng thái Sẵn sàng khi đã đủ khung hình và vector

**Hình:** `figures/H6-trang-thai-lan-xuat-hien.png` (1973×1095). ERD `H8-erd.png` để ở slide dự phòng.

---

## Slide 12 — Công nghệ và hiện thực

**Bố cục:** Bảng 5 hàng. Cột 1 là tầng, cột 2 là logo và tên công nghệ, cột 3 là lý do chính (1 dòng). Bên phải hoặc dưới bảng là 3 điểm hiện thực nổi bật.

**Nội dung, bảng:**

| Tầng | Công nghệ | Lý do chính |
| --- | --- | --- |
| Giao diện | React 19 · Vite · Tailwind CSS | Nhiều tương tác trên một màn hình; dùng được trên điện thoại |
| Máy chủ | Python · Flask 3.1 · SQLAlchemy · Alembic | Cùng ngôn ngữ với mô hình AI; gọn, tường minh |
| AI | YOLO11n · ByteTrack / BoT-SORT · RaSa | Nhanh trên CPU; một không gian chung cho 3 hình thức truy vấn |
| Lưu trữ | PostgreSQL 17 · Milvus 2.6 · MinIO | Ràng buộc toàn vẹn + hàng đợi; lọc trước khi tìm; khung hình riêng tư |
| Camera giả lập | FFmpeg · MediaMTX · Docker Compose | Phát tệp video thành luồng RTSP như camera thật |

**Nội dung, hiện thực nổi bật:**

> - **Danh sách đăng ký mô hình:** chỉ dùng được khi có tệp, mã băm SHA-256 khớp, giấy phép rõ và nạp thử thành công
> - **Tiến trình xử lý nền bền vững:** giữ chỗ công việc 60 giây, gia hạn định kỳ, thử lại khi lỗi
> - **Hàng đợi đặt trong PostgreSQL:** không cần thêm Celery hay Redis

**Hình:** logo chính thức của từng công nghệ (tự tải về); không dùng hình của báo cáo.

---

## Slide 13 — Giao diện và luồng sử dụng

**Bố cục:** Bên trái (65%) đặt H12. Bên phải là 3 thẻ nhỏ theo màu vai trò, mỗi thẻ 1–2 dòng, và một dòng về khả năng dùng trên điện thoại.

**Nội dung:**

> **Quản trị viên**: nhóm Quản trị (tài khoản, camera, mô hình AI, xử lý video) và nhóm Giám sát (trạng thái hệ thống, kiểm tra AI, nhật ký)
> **Giám sát viên**: Tìm kiếm → Chi tiết kết quả → Tạo/thêm vào vụ việc → Vụ việc của tôi
> **Quản lý**: Tổng quan → Danh sách vụ việc → Chi tiết vụ việc (chỉ đọc)
>
> *Giao diện tiếng Việt; menu và đường dẫn bị chặn theo vai trò; đã kiểm thử ở độ rộng 390, 768 và 1440 px.*

**Hình:** `figures/H12-luong-man-hinh.png` (2035×1655).

---

## Slide 14 — Sản phẩm thực tế

**Bố cục:** H10a lớn bên trái (60%). Bên phải là 3 ảnh nhỏ xếp dọc: H10c, H10e, H10f. Mỗi ảnh có chú thích 1 dòng. Có thể thêm viền mảnh hoặc bóng nhẹ, không thêm khung trình duyệt giả.

**Nội dung, chú thích ảnh:**

> - **Tìm kiếm bằng ảnh**: kết quả xếp hạng theo Điểm phù hợp, kèm camera và thời gian
> - **Chi tiết kết quả**: khung hình toàn cảnh có khung bao người được tìm thấy
> - **Vụ việc của Giám sát viên**: trạng thái Đang xử lý / Hoàn thành
> - **Trang tổng quan của Quản lý**: số vụ việc, số kết quả đã lưu, vụ việc gần đây

**Hình:** `figures/H10a-tim-kiem-anh-cat.png` (2234×1262), `figures/H10c-chi-tiet-ket-qua-cat.png` (1568×804), `figures/H10e-vu-viec-cua-toi-cat.png` (2234×962), `figures/H10f-tong-quan-cat.png` (2234×584, rất rộng, nên đặt dưới cùng). Nếu định demo trực tiếp, có thể nói "chuyển sang demo" ngay sau slide này.

---

## Slide 15 — Kiểm thử phần mềm và kịch bản demo

**Bố cục:** Hàng trên gồm 5 thẻ số lớn nằm ngang. Hàng dưới là khung "Phân quyền và bảo mật" với 4 gạch đầu dòng. Góc dưới ghi công cụ kiểm thử.

**Nội dung, 5 thẻ số:**

> **711** kiểm thử đơn vị đạt
> **37** kiểm thử tích hợp đạt (1 bỏ qua) với PostgreSQL, Milvus, MinIO, MediaMTX thật
> **2** kiểm thử đầu cuối đạt với mô hình thật (luồng AI 217 giây)
> **20 màn hình × 3 độ rộng**: không tràn, không lỗi; 3 lỗi phát hiện đã được sửa
> **15/15 bước**: kịch bản demo 3 vai trò, chạy tự động 2 lần liên tiếp (85–88 giây)

**Nội dung, phân quyền và bảo mật:**

> - Gọi **mọi API × mọi vai trò** và cả khi chưa đăng nhập: chỉ vai trò được phép mới được truy cập
> - Vụ việc của người khác hoặc track ngoài khu vực trả về **404**; Quản lý chỉ đọc
> - Mọi thao tác ghi đều cần mã chống giả mạo (CSRF); đăng nhập và tìm kiếm có giới hạn tần suất
> - Tiêu đề bảo mật có ở cả phản hồi thành công lẫn phản hồi lỗi
>
> *Công cụ: pytest (máy chủ), Playwright trên Edge (giao diện).*

**Hình:** không cần; dùng thẻ số và icon.

---

## Slide 16 — Chất lượng tìm kiếm

**Bố cục:** Bên trái (55%) là biểu đồ cột nhóm dựng trong Canva: trục X là R@4, R@8, R@12, R@16; 3 cột cho Ảnh, Văn bản, Thuộc tính; trục Y từ 0 đến 1. Ghi rõ số "0" trên các cột bằng 0 để người xem không tưởng thiếu dữ liệu. Bên phải là 3 khối nhận xét. Dòng điều kiện đo đặt ngay dưới biểu đồ.

**Dữ liệu biểu đồ (lần đánh giá 1):**

| | R@4 | R@8 | R@12 | R@16 | MRR |
| --- | --- | --- | --- | --- | --- |
| Tìm bằng ảnh | 0,833 | 1,0 | 1,0 | 1,0 | 0,867 |
| Tìm bằng văn bản | 0 | 0 | 0 | 0 | 0,01 |
| Tìm theo thuộc tính | 0 | 0 | 0 | 0 | 0,005 |

**Chú thích dưới biểu đồ:**

> *6 truy vấn trên 7 camera WILDTRACK; lần 1: ngưỡng tin cậy 0,25, 1.552 track. Lần 2 (ngưỡng 0,1, 1.526 track, bộ thuộc tính mở rộng) chỉ đo lại thuộc tính: vẫn R@4–16 = 0, MRR 0,0045.*

**Nội dung, nhận xét:**

> **Tìm bằng ảnh tốt:** mọi truy vấn có kết quả đúng trong 8 kết quả đầu
>
> **Văn bản / thuộc tính còn thấp:** không có kết quả đúng trong 16 kết quả đầu; kết quả đúng đầu tiên của các truy vấn thuộc tính nằm ở hạng 87, 241 và 365
> → Nguyên nhân: **khác biệt miền dữ liệu**. RaSa học trên CUHK-PEDES (ảnh một người đã cắt gọn, có câu mô tả viết riêng), còn ảnh người của WILDTRACK được cắt tự động từ cảnh đông người và thường bị che khuất
>
> **Trên dữ liệu demo:** 5 ảnh truy vấn, xem 8 kết quả đầu: 3 truy vấn đạt 8/8, 1 đạt 7/8, 1 đạt 4/8 *(đánh giá bằng mắt, không so sánh với Recall)*
>
> ⇒ Tìm bằng ảnh là hình thức chính; văn bản và thuộc tính là hình thức hỗ trợ.

**Hình:** biểu đồ tự dựng; không dùng 3D.

---

## Slide 17 — Hiệu năng và các hạn chế

**Bố cục:** Chia 2 cột. Cột trái (60%) gồm 3 khối số liệu xếp dọc: bảng N=10/N=20, bảng độ trễ, một dòng bộ nhớ. Cột phải (40%) là khung màu cam "Hạn chế" với 4 gạch đầu dòng. Dòng cấu hình máy đặt nhỏ dưới tiêu đề.

**Nội dung:**

> *Máy triển khai: Intel Core i5-11300H, 16 GB RAM, không GPU rời, chạy toàn bộ trên CPU.*
>
> **Tần suất lấy mẫu** (đoạn video 10 giây, ngưỡng 0,1)
>
> | | N = 10 | N = 20 |
> | --- | --- | --- |
> | Thời gian xử lý | 149,5 s | 132,6 s |
> | Thời gian CPU | ~212 s | ~160 s |
> | Số track (track ngắn < 2 s) | 44 (22) | 36 (24) |
> | Dung lượng ảnh | 10,2 MB | 6,9 MB |
>
> → Chọn **N = 20**. Phần lớn thời gian nằm ở bộ mã hóa ảnh (~1,85 s mỗi track).
>
> **Độ trễ tìm kiếm** (30 lượt, k = 8, 1.523 track)
>
> | | Trung vị | Phân vị 95 |
> | --- | --- | --- |
> | Ảnh | 1.269 ms | 1.976 ms |
> | Văn bản | 106 ms | 142 ms |
> | Thuộc tính | 103 ms | 136 ms |
>
> Lần tìm đầu tiên ~31 s (nạp bộ mã hóa), nên cần làm nóng trước khi dùng.
>
> **Bộ nhớ:** ~3,7 GiB khi rảnh, ~8,0 GiB khi đang xử lý (cận trên)
>
> **Hạn chế**
> - Tìm bằng văn bản/thuộc tính chưa hiệu quả trên WILDTRACK
> - Chậm hơn thời gian thực ~7 lần → xử lý luân phiên camera; dữ liệu demo lập chỉ mục từ tệp video
> - RTSP ghi theo phiên, nên phải chờ tới khi tìm được; mốc thời gian lấy theo đồng hồ đọc nên track dễ bị tách
> - BoT-SORT đã tích hợp nhưng chưa được đánh giá

**Hình:** không cần.

---

## Slide 18 — Kết quả đạt được và hướng phát triển

**Bố cục:** Chia 50/50. Cột trái là 5 mục tiêu, mỗi dòng có dấu ✔ (hoặc △ cho phần còn hạn chế) và bằng chứng ngắn. Cột phải là 5 hướng phát triển, mỗi hướng một icon.

**Nội dung, kết quả đạt được:**

> ✔ **Dữ liệu camera → tìm kiếm được**: 1.488 track từ 7 camera, lập chỉ mục không lỗi
> ✔/△ **Ba hình thức truy vấn**: đã hiện thực đủ; tìm bằng ảnh tốt, văn bản/thuộc tính còn thấp
> ✔ **Đánh giá và vụ việc**: xem trên khung hình gốc; vụ việc có trạng thái; Quản lý theo dõi
> ✔ **Phân quyền**: 3 vai trò, lọc theo khu vực, kiểm thử trên mọi API
> ✔ **Đánh giá mô hình có sẵn**: có số liệu chất lượng, tốc độ và bộ nhớ trên CPU
>
> *Luồng nghiệp vụ trọn vẹn: kịch bản demo 15/15 bước × 2 lần.*

**Nội dung, hướng phát triển:**

> - **Chất lượng văn bản:** xếp hạng lại bằng bộ so khớp ảnh–văn bản của RaSa; tinh chỉnh trên dữ liệu cùng miền
> - **Tốc độ:** OpenVINO hoặc GPU để xử lý liên tục, ghi ngay khi track kết thúc
> - **RTSP:** lấy mốc thời gian từ dấu thời gian của luồng
> - **Đánh giá:** đo lại Recall với cấu hình hiện hành; so sánh ByteTrack và BoT-SORT
> - **Mở rộng:** liên kết một người giữa nhiều camera, nhiều khung hình cho mỗi track, truy vấn tiếng Việt

**Hình:** không cần.

---

## Slide 19 — Cảm ơn và câu hỏi

**Bố cục:** Nền là H10a làm tối khoảng 70% hoặc làm mờ; hoặc dùng nền trơn. Chữ đặt giữa slide.

**Nội dung:**

> **Em xin chân thành cảm ơn quý Thầy Cô đã lắng nghe!**
> Hỏi & Đáp
>
> PRISM — Person Retrieval via Image & Semantic Matching
> Nguyễn Công Huy — 2113499

**Hình:** `figures/H10a-tim-kiem-anh-cat.png` (làm nền), hoặc để nền trơn.

---

## Slide dự phòng (sau slide 19, chỉ mở khi được hỏi)

| Câu hỏi có thể gặp | Hình |
| --- | --- |
| Use case chi tiết | `H1-use-case.png` toàn màn hình |
| Lưu vụ việc diễn ra thế nào | `H5-tuan-tu-vu-viec.png` |
| Vòng đời công việc, thử lại, hủy | `H7-trang-thai-cong-viec.png` |
| Cơ sở dữ liệu | `H8-erd.png` |
| Chức năng của Quản trị viên | lưới 2×2: `H10g-camera-cat.png`, `H10h-mo-hinh-ai-cat.png`, `H10j-trang-thai-he-thong-cat.png`, `H10k-kiem-tra-ai-cat.png` |
| Tìm theo thuộc tính, tạo vụ việc | `H10b-tim-kiem-thuoc-tinh-cat.png`, `H10d-tao-vu-viec-cat.png` |

## Những câu cần tránh khi trình bày

- "Nhận diện khuôn mặt", "xác định danh tính" → nói "hỗ trợ tìm kiếm và xếp hạng".
- "Huấn luyện/tinh chỉnh mô hình", "xử lý đồng thời 7 camera", "thời gian thực".
- "Recall ảnh 0,83 với cấu hình hiện hành" → số này thuộc lần đo 1, ngưỡng 0,25.
- "Thuộc tính là mô hình riêng", "hỗ trợ tiếng Việt".
- "Điểm phù hợp được lưu trong vụ việc".
