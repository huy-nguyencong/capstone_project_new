# Kịch bản demo PRISM

> Tài liệu thực hiện cho buổi bảo vệ (R7 trong `remaining-work-plan.md`); không phải nguồn yêu cầu.
> Luồng trình diễn bám theo architect §1/§10, theo thứ tự Giám sát viên tìm kiếm và lưu vụ việc → Quản lý
> theo dõi → Quản trị viên thiết lập camera RTSP, bật AI, kiểm tra và đổi mô hình.

## 1. Tóm tắt

| Phần | Vai trò | Nội dung | Thời gian thao tác |
| --- | --- | --- | --- |
| 4.1 | Giám sát viên | G1–G9: tìm bằng ảnh, xem chi tiết, tạo vụ việc và đánh dấu hoàn thành, vụ việc của tôi, tìm bằng văn bản, từ văn bản sang ảnh, thuộc tính | ~1,5 phút |
| 4.2 | Quản lý | Q1–Q3: tổng quan, hồ sơ vụ việc | ~15 giây |
| 4.3 | Quản trị viên | A1–A7: thêm camera RTSP, bật AI, tiến trình nền tự xử lý, kiểm tra AI, đổi mô hình, nhật ký, tắt AI | ~1 phút thao tác + vài phút chờ (bật AI, kiểm tra AI, đổi mô hình) |

Thời gian thao tác đo khi diễn tập tự động (2026-09-28, hai lần liên tiếp đều đạt): 85–88 giây chưa kể
lời thuyết minh. Bản tự động (mục 7) chạy theo thứ tự cũ Quản trị viên → Giám sát viên → Quản lý và
không gồm G5–G8, A4–A6; nội dung kiểm tra tương đương. Khi trình bày có lời nói, dự kiến 6–8 phút.

Dữ liệu demo: 7 camera WILDTRACK (khu vực Gate A), 1.488 track trong 2 phút đầu của mỗi video, cùng
camera `RTSP Cam 1` (35 track) và 1 vụ việc có sẵn ("Tìm người để quên hành lý", 3 kết quả); tổng
1.523 track. Mốc dữ liệu: `backups/20260928T184653Z` (đã verify, đã thử `demo-reset.ps1`).

## 2. Chuẩn bị trước ngày bảo vệ

- [ ] Máy cắm sạc, tắt chế độ ngủ; đóng trình duyệt/IDE không cần thiết (RAM máy 16 GB chỉ còn ~2 GB
      trống khi chạy đủ stack).
- [ ] Chạy trọn kịch bản ít nhất một lần bằng tay trên chính máy demo; sau đó đưa dữ liệu về mốc
      (mục 6).
- [ ] Quay video màn hình có thuyết minh làm phương án dự phòng, theo thứ tự mục 4. Bản dự phòng không lời do diễn tập tự
      động tạo: `frontend/ui-smoke/output/demo/2026-09-28T18-28-24/demo.mp4` (83 giây). Chép video ra
      USB/Drive.
- [ ] Chép ảnh truy vấn `backend/var/demo-queries/WT-Q00*.jpg` ra màn hình desktop để kéo thả nhanh.

## 3. Trước giờ bảo vệ (khoảng 30 phút)

1. Mở Docker Desktop, rồi ở thư mục gốc:
   ```powershell
   .\scripts\storage.ps1 up
   .\scripts\rtsp.ps1 up          # in ra 7 địa chỉ rtsp://<IP-LAN>:8554/cam1..7
   ```
2. **Nếu IP in ra khác `PERSON_SEARCH_RTSP_NETWORKS` trong `backend/.env`** (đổi mạng Wi-Fi): sửa dòng
   này thành `<IP-LAN>/32`. Camera `RTSP Cam 1` cũ vẫn trỏ IP cũ; không cần sửa vì nó đang tắt AI và
   không dùng trong kịch bản.
3. Mở ba terminal PowerShell, bắt đầu từ thư mục gốc repo:
   ```powershell
   # Terminal 1 — API
   cd backend
   .\.venv\Scripts\Activate.ps1
   python -m person_search

   # Terminal 2 — worker
   cd backend
   .\.venv\Scripts\Activate.ps1
   person-search-production-worker

   # Terminal 3 — giao diện
   cd frontend
   npm run dev
   ```
   Kích hoạt thành công thì đầu dòng lệnh hiện `(.venv)`. Nếu PowerShell báo không được chạy script
   (`running scripts is disabled`), chạy `Set-ExecutionPolicy -Scope Process Bypass` trong terminal đó
   rồi kích hoạt lại; lệnh chỉ có hiệu lực cho terminal hiện tại. Mở `http://localhost:5173`.
4. **Làm nóng tìm kiếm (bắt buộc):** đăng nhập `operator`, tìm bằng ảnh `WT-Q006.jpg` một lần. Lần tìm
   đầu sau khi API khởi động phải nạp encoder RaSa (~30 giây); nếu để đến lúc demo, cùng lúc worker
   đang xử lý RTSP, lần tìm đầu mất tới ~100 giây. Sau đó đăng xuất.
5. Đăng nhập `admin`, trang **Trạng thái hệ thống**: bốn dịch vụ nền "Hoạt động", worker `IDLE`
   ("Sẵn sàng"), không camera nào báo lỗi.

## 4. Kịch bản trình diễn

Thứ tự: **Giám sát viên → Quản lý → Quản trị viên**. Phần tìm kiếm chạy trước, khi tiến trình nền còn
rảnh nên kết quả ra nhanh; phần Quản trị viên (bật AI, kiểm tra AI, đổi mô hình) tốn thời gian chờ nên
để cuối. Đã làm nóng tìm kiếm ở mục 3.

Tài khoản: `operator`, `viewer`, `admin` (mật khẩu seed). Ảnh truy vấn ở `backend/var/demo-queries/`
(đã chép ra desktop theo mục 2).

### 4.1. Giám sát viên (`operator`) — tìm kiếm và lập vụ việc

#### G1. Đăng nhập, màn hình tìm kiếm

- **Dữ liệu:** tài khoản `operator`.
- **Thao tác:** đăng nhập → trang **Tìm kiếm người**.
- **Kết quả mong đợi:** góc phải hiện "Khu vực giám sát: Gate A"; danh sách camera chỉ gồm camera của
  Gate A; ba cách tìm Hình ảnh, Văn bản, Thuộc tính.
- **Lời thuyết trình:** "Giám sát viên chỉ tìm được trên camera thuộc khu vực của mình, ở đây là Gate A."

#### G2. Tìm bằng ảnh

- **Dữ liệu:** ảnh `WT-Q006.jpg` (người đội mũ len, mang túi hoa, giày trắng); số kết quả 8.
- **Thao tác:** tab **Hình ảnh** → kéo thả ảnh vào ô (hoặc bấm chọn tệp, hoặc dán Ctrl+V) →
  **Tìm kiếm**.
- **Kết quả mong đợi:** khoảng 1–2 giây; 8 kết quả đều là người này, trên Cam 6, 4, 1, 7, 3; điểm
  khoảng 0,85–0,88.
- **Lời thuyết trình:** "Tìm bằng một ảnh crop: tám kết quả đều là người này, xuất hiện trên năm camera khác nhau. Điểm chỉ dùng để xếp hạng, kết luận thuộc về người dùng."

#### G3. Xem chi tiết một kết quả

- **Dữ liệu:** không.
- **Thao tác:** bấm kết quả #1; dùng nút mũi tên để xem kết quả tiếp theo.
- **Kết quả mong đợi:** khung hình toàn cảnh có viền đánh dấu người; bên cạnh là ảnh người, điểm phù
  hợp, camera, khu vực, thời gian.
- **Lời thuyết trình:** "Khung hình gốc có viền đánh dấu người, kèm camera, khu vực và thời gian xuất hiện."

#### G4. Tạo vụ việc và đánh dấu hoàn thành khi lưu

- **Dữ liệu:** tiêu đề `Tìm người mang túi hoa, giày trắng`; ghi chú
  `Đã xác định người trên nhiều camera khu Gate A.`
- **Thao tác:** trong cửa sổ chi tiết → **Tạo vụ việc mới** → nhập tiêu đề, ghi chú → bật
  **Đánh dấu vụ việc đã hoàn thành** → **Tạo vụ việc** → đóng cửa sổ.
- **Kết quả mong đợi:** thông báo đã lưu.
- **Lời thuyết trình:** "Lưu kết quả vào vụ việc mới và đánh dấu hoàn thành ngay khi lưu; vụ việc hoàn thành sẽ bị khóa."

#### G5. Vụ việc của tôi

- **Dữ liệu:** không.
- **Thao tác:** **Vụ việc của tôi** → tab **Hoàn thành** → mở vụ việc vừa tạo; chỉ vào nút
  **Mở lại vụ việc** (không cần bấm).
- **Kết quả mong đợi:** vụ việc có 1 kết quả, trạng thái Hoàn thành; vụ việc có sẵn "Tìm người để quên
  hành lý" nằm ở tab Đang xử lý.
- **Lời thuyết trình:** "Vụ việc lọc theo trạng thái; vụ việc hoàn thành có thể mở lại khi cần bổ sung."

#### G6. Tìm bằng mô tả văn bản

- **Dữ liệu:** `A woman with long blonde hair wearing a black jacket.`
- **Thao tác:** **Tìm kiếm người** → tab **Văn bản** → gõ câu → **Tìm kiếm**.
- **Kết quả mong đợi:** dưới 1 giây; khoảng 7/8 kết quả là phụ nữ tóc vàng dài, áo khoác tối, trên
  nhiều camera; điểm khoảng 0,3.
- **Lời thuyết trình:** "Tìm bằng mô tả tiếng Anh: phần lớn kết quả khớp mô tả; điểm thấp hơn tìm bằng ảnh là bình thường."

#### G7. Từ văn bản sang ảnh

- **Dữ liệu:** `A man carrying an orange backpack and pulling a black suitcase.`
- **Thao tác:** tab **Văn bản** → gõ câu → **Tìm kiếm** → chuyển sang tab **Hình ảnh** (lưới kết quả
  vẫn giữ) → kéo thẻ kết quả **#1** thả vào ô ảnh → **Tìm kiếm**.
- **Kết quả mong đợi:** văn bản: 4/8 là người đeo ba lô cam kéo vali, trên Cam 6, 4, 1. Ảnh: 8/8 đúng
  người đó trên Cam 6 và 4 (kết quả #1 là chính lần xuất hiện vừa kéo vào).
- **Lời thuyết trình:** "Văn bản để khoanh vùng; thấy đúng người thì kéo kết quả sang tìm bằng ảnh, lúc này tám kết quả đều là người đó."

#### G8. Tìm bằng thuộc tính

- **Dữ liệu:** Giới tính `Woman` · Loại áo `Coat` · Màu áo `Black`.
- **Thao tác:** tab **Thuộc tính** → chọn ba giá trị → xem câu được sinh ra → **Tìm kiếm**.
- **Kết quả mong đợi:** câu `A woman wearing a black coat.`; khoảng 6/8 là phụ nữ mặc áo khoác dài tối
  màu.
- **Lời thuyết trình:** "Chọn thuộc tính, hệ thống ghép thành câu tiếng Anh. Mô hình nhận tốt giới tính, tóc, đồ mang theo, kém với màu sáng."

#### G9. Đăng xuất

### 4.2. Quản lý (`viewer`) — theo dõi kết quả

#### Q1. Tổng quan

- **Dữ liệu:** tài khoản `viewer`.
- **Thao tác:** đăng nhập → **Tổng quan**.
- **Kết quả mong đợi:** 2 vụ việc, 4 kết quả đã lưu, 1 đang xử lý, 1 hoàn thành; vụ việc vừa tạo ở đầu
  danh sách "Vụ việc gần đây".
- **Lời thuyết trình:** "Quản lý theo dõi toàn hệ thống: số vụ việc theo trạng thái và số kết quả đã lưu; vụ việc vừa tạo nằm đầu danh sách."

#### Q2. Hồ sơ vụ việc

- **Dữ liệu:** không (có thể lọc theo người phụ trách `Operator` hoặc tab trạng thái).
- **Thao tác:** **Hồ sơ vụ việc** → mở vụ việc `Tìm người mang túi hoa, giày trắng`.
- **Kết quả mong đợi:** chi tiết vụ việc chỉ đọc, có ảnh kết quả, thời gian hoàn thành; không có nút
  sửa.
- **Lời thuyết trình:** "Hồ sơ vụ việc ở chế độ chỉ đọc, xem được cả ảnh kết quả."

#### Q3. Đăng xuất

### 4.3. Quản trị viên (`admin`) — vận hành camera và AI

URL RTSP: dùng địa chỉ `cam2` do `rtsp.ps1 up` in ra, ví dụ `rtsp://192.168.110.147:8554/cam2`
(IP đổi theo mạng; gõ sai IP hoặc gõ nguyên chữ mẫu thì camera lưu được nhưng ở trạng thái
"Chưa xác minh").

#### A1. Thêm camera RTSP và kiểm tra kết nối

- **Dữ liệu:** mã `DEMO-RTSP`; tên `Camera sảnh chính (RTSP)`; khu vực `Gate A`; RTSP như trên.
- **Thao tác:** đăng nhập `admin` → **Camera** → **Thêm camera** → nhập → **Lưu và kiểm tra RTSP**.
- **Kết quả mong đợi:** camera mới, cột Kết nối "Trực tuyến".
- **Lời thuyết trình:** "Thêm một camera RTSP vào khu vực Gate A và kiểm tra kết nối: camera trực tuyến."

#### A2. Bật xử lý AI

- **Dữ liệu:** không.
- **Thao tác:** **Xử lý AI** → bật công tắc của `Camera sảnh chính (RTSP)` → xác nhận **Bật xử lý AI**.
- **Kết quả mong đợi:** công tắc bật; đầu trang hiện cấu hình đang dùng YOLO11n + ByteTrack.
- **Lời thuyết trình:** "Bật xử lý AI cho camera vừa thêm."

#### A3. Tiến trình nền tự xử lý

- **Dữ liệu:** không.
- **Thao tác:** **Trạng thái hệ thống** → bấm **Làm mới** sau 10–20 giây.
- **Kết quả mong đợi:** camera mới "Đang xử lý"; dòng tiến trình nền "Đang xử lý". Chờ thực tế 13–24
  giây.
- **Lời thuyết trình:** "Tiến trình nền tự nhận camera và bắt đầu xử lý luồng, không cần thao tác thêm."

#### A4. Kiểm tra AI

- **Dữ liệu:** camera `Camera sảnh chính (RTSP)` (hoặc `RTSP Cam 1`).
- **Thao tác:** **Kiểm tra AI** → mục kiểm tra luồng xử lý camera → chọn camera → chạy kiểm tra.
- **Kết quả mong đợi:** vài chục giây (chưa đo chính xác); các bước Nguồn khung hình (6 khung
  1920×1080), Detector (hàng chục đến hơn 100 vùng người; thử trên `RTSP Cam 1` được 107–126), Tracker, Image Encoder (vector 256 chiều) đều
  thành công, mỗi bước có thời gian.
- **Lời thuyết trình:** "Kiểm tra AI chạy thử từng bước của luồng xử lý trên camera và báo kết quả, thời gian từng bước."

#### A5. Đổi mô hình theo dõi

- **Dữ liệu:** Tracker `BoT-SORT`.
- **Thao tác:** **Mô hình AI** → chọn thẻ BoT-SORT → **Áp dụng cấu hình** → chờ "Đang áp dụng…".
- **Kết quả mong đợi:** vài chục giây (chưa đo chính xác); nhãn "Đang dùng" chuyển sang BoT-SORT. Các
  mô hình "Không khả dụng" (YOLO small, YOLOX) không chọn được.
- **Lời thuyết trình:** "Đổi Tracker sang BoT-SORT; hệ thống nạp thử mô hình trước khi áp dụng nên mất vài chục giây."

#### A6. Nhật ký hệ thống

- **Dữ liệu:** không.
- **Thao tác:** **Nhật ký hệ thống**.
- **Kết quả mong đợi:** các sự kiện vừa thực hiện ở đầu danh sách: tạo camera, kiểm tra kết nối, bật
  AI, đổi cấu hình mô hình, tạo và đóng vụ việc, đăng nhập/đăng xuất.
- **Lời thuyết trình:** "Các thao tác vừa thực hiện đều được ghi nhật ký với người thực hiện và thời gian."

#### A7. Kết thúc

- **Thao tác:** **Xử lý AI** → tắt công tắc của `Camera sảnh chính (RTSP)` → **Tắt xử lý AI**; nếu
  muốn, đổi lại Tracker về ByteTrack ở **Mô hình AI**.
- **Lời thuyết trình:** "Tắt xử lý AI; dữ liệu đã phân tích được giữ nguyên."

Sau buổi trình diễn hoặc diễn tập: tắt API và worker, chạy `demo-reset.ps1` (mục 6) để đưa dữ liệu và
cấu hình mô hình về mốc.

### Truy vấn thay thế (nếu hội đồng muốn xem thêm)

Ảnh ở `backend/var/demo-queries/`, đã thử trên dữ liệu demo (top 8, kiểm tra bằng mắt):

| Ảnh | Đặc điểm | Đúng / 8 | Camera có kết quả đúng |
| --- | --- | --- | --- |
| `WT-Q006.jpg` | túi hoa, giày trắng, mũ len | 8 | Cam 6, 4, 1, 7, 3 |
| `WT-Q002.jpg` | ba lô cam, kéo vali | 8 | Cam 4, 1, 7, 6 |
| `WT-Q001.jpg` | ba lô xanh caro | 8 | Cam 7, 5, 6, 1 |
| `WT-Q004.jpg` | túi đeo trắng, túi đen | 7 | Cam 3, 2, 4, 1 |
| `WT-Q003.jpg` (dự phòng) | túi đeo vàng-đen | 4 | Cam 5, 7 |

Tìm bằng văn bản/thuộc tính chạy được nhưng Recall thấp trên WILDTRACK (architect §13: miền dữ liệu
khác CUHK-PEDES). Nếu được hỏi, trình diễn như chức năng hỗ trợ và giải thích giới hạn, không dùng
làm phần chính.

### Truy vấn văn bản và thuộc tính đã thử

Thử trên dữ liệu demo ngày 2026-10-01 (1.523 track, top 8, tài khoản `operator`, xem bằng mắt). Cột
"Khớp / 8" đếm số kết quả **đúng với mô tả** (giới tính, tóc, quần áo, đồ mang theo), không phải số
lần tìm ra cùng một người. Điểm phù hợp của văn bản/thuộc tính chỉ khoảng 0,25–0,33 (tìm bằng ảnh
khoảng 0,8); đó là bình thường khi so ảnh với câu chữ, không phải lỗi.

**Văn bản** (gõ nguyên câu ở tab Văn bản):

| Câu mô tả | Khớp / 8 | Ghi chú |
| --- | --- | --- |
| `A woman with long blonde hair wearing a black jacket.` | 7 | Tốt nhất; phụ nữ tóc vàng dài trên Cam 2, 3, 5, 6, 7 |
| `A woman with long hair wearing a black coat and a scarf.` | 6 | |
| `A young man with glasses wearing a black jacket and carrying a backpack.` | 5–6 | |
| `A man carrying an orange backpack and pulling a black suitcase.` | 4 | 4 kết quả là **đúng một người** (người kéo vali ở `WT-Q002`) trên Cam 6, 4, 1. Kéo kết quả #1 vào ô ảnh rồi tìm bằng ảnh: 8/8 đúng người này trên Cam 6 và Cam 4 (kết quả #1 là chính track vừa kéo vào) |
| `A man wearing a black jacket and blue jeans, carrying a backpack.` | 5 | Câu chung, nhiều người khớp |

**Thuộc tính** (chọn ở tab Thuộc tính; câu tiếng Anh được sinh tự động):

| Chọn trên giao diện | Câu sinh ra | Khớp / 8 |
| --- | --- | --- |
| Giới tính `Woman` · Loại áo `Coat` · Màu áo `Black` | `A woman wearing a black coat.` | 6 |
| Giới tính `Woman` · Loại áo `Jacket` · Màu áo `Black` · Loại quần/váy `Jeans` · Màu quần/váy `Blue` | `A woman wearing a black jacket and blue jeans.` | 6 |
| Giới tính `Man` · Vật mang theo `Backpack` | `A man carrying a backpack.` | 6 |
| Giới tính `Man` · Loại áo `Jacket` · Màu áo `Black` · Vật mang theo `Backpack` | `A man wearing a black jacket, carrying a backpack.` | 5–6 |

**Tránh dùng khi demo** (đã thử, không đạt): màu sáng hoặc nổi (áo đỏ, be, trắng, xanh dương sáng,
hoodie xám) — kết quả chỉ đúng giới tính, sai màu; họa tiết và màu túi (túi hoa, túi vàng-đen) — 0/8.
Mô hình nhận tốt giới tính, tóc dài/tóc vàng, ba lô, vali và quần áo tối màu; kém với màu sắc cụ thể.

**Cách trình bày gợi ý:** tìm bằng văn bản câu vali ở trên → mở kết quả #1 → kéo vào ô ảnh và tìm
bằng ảnh → 8/8 cùng một người (đã thử 2026-10-01; kết quả #1 là chính track vừa kéo vào, 7 kết quả còn lại là các lần xuất hiện khác trên Cam 6 và Cam 4). Luồng này cho thấy văn bản dùng để khoanh vùng ban đầu,
ảnh dùng để xác định chính xác.

## 5. Sự cố và phương án dự phòng

| Hiện tượng | Xử lý |
| --- | --- |
| Tìm kiếm quay lâu, báo không kết nối được | Chưa làm nóng (mục 3.4). Chờ ~1 phút rồi tìm lại; lần sau nhanh. |
| A1 báo "Mất kết nối" hoặc lỗi địa chỉ không được phép | IP đổi: kiểm tra `rtsp.ps1 status`, sửa `PERSON_SEARCH_RTSP_NETWORKS`, khởi động lại API và worker. Nếu không kịp, bỏ A1–A3, làm tiếp A4–A6 với `RTSP Cam 1` hoặc camera WILDTRACK và nói phần RTSP bằng video. |
| A3 camera không lên "Đang xử lý" sau 1 phút | Kiểm tra terminal worker; trang Trạng thái hệ thống phải thấy worker có heartbeat. Có thể bỏ qua: tìm kiếm dùng dữ liệu đã lập chỉ mục. |
| Trang trắng hoặc lỗi giao diện | Tải lại trang (F5); đăng nhập lại. |
| Máy/mạng hỏng hẳn | Chiếu video dự phòng (mục 2). |
| Dữ liệu demo hỏng | Dừng API/worker, `.\scripts\demo-reset.ps1` (~70 giây), khởi động lại. |

## 6. Sau mỗi lần diễn tập

Diễn tập ghi thêm dữ liệu (camera `DEMO-RTSP`, vụ việc, track từ phiên RTSP, audit). Trả về mốc:

```powershell
# dừng API và worker (Ctrl+C), giữ storage chạy
.\scripts\demo-reset.ps1                    # mặc định bản sao lưu mới nhất trong backups/
```

Script khôi phục PostgreSQL/MinIO/Milvus từ bản sao lưu, xóa ảnh/vector sinh ra sau mốc rồi chạy
`reconcile`; báo lỗi nếu API/worker còn chạy. Nếu thay đổi dữ liệu demo có chủ đích, tạo mốc mới:
`python tools/storage_backup.py backup` rồi `verify`.

## 7. Diễn tập tự động

`frontend/ui-smoke/demo-run.mjs` chạy đúng các bước A–D ở 1440×900 và quay video (Edge có sẵn,
`playwright-core`); có bước làm nóng tìm kiếm không quay:

```powershell
cd frontend
$env:DEMO_RTSP_URL = 'rtsp://192.168.110.145:8554/cam2'   # IP theo rtsp.ps1 up
npm run ui:demo           # ghi dữ liệu: chạy trên mốc rồi demo-reset.ps1
```

Kết quả nằm ở `frontend/ui-smoke/output/demo/<thời điểm>/` (`demo.webm`, ảnh từng bước). Chuyển sang
MP4: `ffmpeg -i demo.webm -c:v libx264 -pix_fmt yuv420p demo.mp4`.
