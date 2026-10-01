# Kịch bản demo PRISM

> Tài liệu thực hiện cho buổi bảo vệ (R7 trong `remaining-work-plan.md`); không phải nguồn yêu cầu.
> Luồng trình diễn bám theo architect §1/§10: Quản trị viên thiết lập camera RTSP, hệ thống tự xử lý,
> Giám sát viên tìm kiếm và lưu vụ việc, Quản lý theo dõi.

## 1. Tóm tắt

| Phần | Vai trò | Nội dung | Thời gian thao tác |
| --- | --- | --- | --- |
| A | Quản trị viên | Thêm camera RTSP, kiểm tra kết nối, bật AI, xem worker tự tạo phiên | ~40 giây |
| B | Giám sát viên | Tìm bằng ảnh, mở kết quả, tạo vụ việc và đánh dấu hoàn thành; tìm bằng văn bản (kể cả văn bản rồi đến ảnh) và thuộc tính | ~25 giây + ~1 phút cho B5–B7 |
| C | Quản lý | Dashboard, mở hồ sơ vụ việc | ~15 giây |
| D | Quản trị viên | Tắt AI cho camera vừa thêm | ~10 giây |

Thời gian thao tác đo khi diễn tập tự động (2026-09-28, hai lần liên tiếp đều đạt): 85–88 giây chưa kể
lời thuyết minh; bản tự động không gồm B5–B7 (tìm bằng văn bản/thuộc tính, thêm ~1 phút). Khi trình bày có lời nói, dự kiến 6–8 phút.

Dữ liệu demo: 7 camera WILDTRACK (khu vực Gate A), 1.488 track trong 2 phút đầu của mỗi video, cùng
camera `RTSP Cam 1` (35 track) và 1 vụ việc có sẵn ("Tìm người để quên hành lý", 3 kết quả); tổng
1.523 track. Mốc dữ liệu: `backups/20260928T184653Z` (đã verify, đã thử `demo-reset.ps1`).

## 2. Chuẩn bị trước ngày bảo vệ

- [ ] Máy cắm sạc, tắt chế độ ngủ; đóng trình duyệt/IDE không cần thiết (RAM máy 16 GB chỉ còn ~2 GB
      trống khi chạy đủ stack).
- [ ] Chạy trọn kịch bản ít nhất một lần bằng tay trên chính máy demo; sau đó đưa dữ liệu về mốc
      (mục 6).
- [ ] Quay video màn hình có thuyết minh làm phương án dự phòng (cách quay ở mục 8). Bản dự phòng không lời do diễn tập tự
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

Tài khoản demo: `admin`, `operator`, `viewer` (mật khẩu seed). URL RTSP dùng trong demo, trên mạng
hiện tại: **`rtsp://192.168.110.145:8554/cam2`**. Nếu `rtsp.ps1 up` in IP khác thì dùng đúng địa chỉ
`cam2` nó in ra; gõ nguyên chữ `<IP-LAN>` sẽ lưu được camera nhưng kết nối ở trạng thái "Chưa xác minh".

### A. Quản trị viên — nhận luồng RTSP (UC-03, UC-04, UC-06)

| # | Thao tác | Kết quả mong đợi | Ý để nói |
| --- | --- | --- | --- |
| A1 | **Camera → Thêm camera**: mã `DEMO-RTSP`, tên `Camera sảnh chính (RTSP)`, khu vực Gate A, RTSP `rtsp://192.168.110.145:8554/cam2` (IP theo `rtsp.ps1 up`) → **Lưu và kiểm tra RTSP** | Camera mới, cột Kết nối "Trực tuyến" | Hệ thống camera giả lập: FFmpeg phát 7 video WILDTRACK vào MediaMTX; địa chỉ phải thuộc dải mạng cho phép (chống SSRF) |
| A2 | **Xử lý AI** → bật công tắc của camera → **Bật xử lý AI** | Công tắc bật; cấu hình YOLO11n + ByteTrack hiển thị ở đầu trang | Detector/Tracker là cấu hình chung; Admin đổi được ở **Mô hình AI** (có BoT-SORT) |
| A3 | **Trạng thái hệ thống** → **Làm mới** sau ~10–20 giây | Camera mới "Đang xử lý", worker "Đang xử lý" | Worker tự lập lịch phiên RTSP (1.800 frame, lấy mẫu mỗi 20 frame), tuần tự từng camera |
| A4 | Đăng xuất | | |

### B. Giám sát viên — tìm và lưu vụ việc (UC-09, UC-10, UC-11)

| # | Thao tác | Kết quả mong đợi | Ý để nói |
| --- | --- | --- | --- |
| B1 | Đăng nhập `operator` → **Tìm kiếm người** → tab **Hình ảnh** → kéo thả `WT-Q006.jpg` → **Tìm kiếm** | ~8 giây; 8 kết quả, cùng một người (túi hoa, giày trắng) trên Cam 6, 4, 1, 7, 3 | Chỉ tìm trong khu vực được giao; điểm phù hợp chỉ để xếp hạng; mỗi kết quả là một lần xuất hiện (track) |
| B2 | Bấm kết quả #1 | Khung hình toàn cảnh có viền người, điểm, camera, thời gian | Ảnh crop dựng động từ full frame + bbox, không lưu crop |
| B3 | **Tạo vụ việc mới**: tiêu đề `Tìm người mang túi hoa, giày trắng`, ghi chú, bật **Đánh dấu vụ việc đã hoàn thành** → **Tạo vụ việc** → đóng | Thông báo đã lưu | Không lưu điểm vào vụ việc; vụ việc hoàn thành bị khóa, mở lại được |
| B4 | **Vụ việc của tôi** → tab **Hoàn thành** → mở vụ việc | Vụ việc có 1 kết quả, trạng thái Hoàn thành | |
| B5 | **Tìm kiếm người** → tab **Văn bản** → gõ `A woman with long blonde hair wearing a black jacket.` → **Tìm kiếm** | Khoảng 1 giây hoặc nhanh hơn (đo lúc worker rảnh: ~0,1 s); khoảng 7/8 kết quả là phụ nữ tóc vàng dài, áo khoác tối, trên nhiều camera | Mô tả chỉ nhận tiếng Anh (gõ tiếng Việt có dấu bị từ chối); câu và ảnh được RaSa đưa vào cùng một không gian vector nên dùng chung chỉ mục với tìm bằng ảnh; điểm chỉ ~0,3 là bình thường khi so câu chữ với ảnh |
| B6 | Tab **Văn bản** → gõ `A man carrying an orange backpack and pulling a black suitcase.` → **Tìm kiếm** → chuyển sang tab **Hình ảnh** (lưới kết quả vẫn giữ) → kéo thẻ kết quả **#1** trong lưới thả vào ô ảnh → **Tìm kiếm** | Văn bản: 4/8 là người đeo ba lô cam kéo vali, trên Cam 6, 4, 1. Ảnh: 8/8 đúng người đó trên Cam 6 và 4 (kết quả #1 là chính track vừa kéo vào) | Văn bản dùng để khoanh vùng khi chưa có ảnh; khi đã thấy người cần tìm thì chuyển sang tìm bằng ảnh để xác định chính xác |
| B7 | Tab **Thuộc tính** → Giới tính `Woman`, Loại áo `Coat`, Màu áo `Black` → **Tìm kiếm** | Câu `A woman wearing a black coat.` được sinh ra; khoảng 6/8 là phụ nữ mặc áo khoác dài tối màu | Thuộc tính được ghép thành câu tiếng Anh có kiểm soát rồi đi qua cùng Text Encoder. Nói rõ giới hạn: mô hình nhận tốt giới tính, tóc, ba lô/vali và áo tối màu, nhưng kém với màu sáng (đỏ, be, trắng); Recall theo danh tính bằng văn bản/thuộc tính trên WILDTRACK là 0 |
| B8 | Đăng xuất | | |

### C. Quản lý — theo dõi (UC-12, UC-13, UC-14)

| # | Thao tác | Kết quả mong đợi |
| --- | --- | --- |
| C1 | Đăng nhập `viewer` → **Tổng quan** | 2 vụ việc, 4 kết quả, 1 đang xử lý, 1 hoàn thành; vụ việc mới ở đầu danh sách |
| C2 | **Hồ sơ vụ việc** → mở vụ việc mới | Chỉ đọc; ảnh kết quả hiển thị |
| C3 | Đăng xuất | |

### D. Kết thúc

Đăng nhập `admin` → **Xử lý AI** → tắt công tắc của `Camera sảnh chính (RTSP)` → **Tắt xử lý AI**.

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
| A1 báo "Mất kết nối" hoặc lỗi địa chỉ không được phép | IP đổi: kiểm tra `rtsp.ps1 status`, sửa `PERSON_SEARCH_RTSP_NETWORKS`, khởi động lại API và worker. Nếu không kịp, bỏ phần A, nói bằng ảnh chụp trạng thái và video. |
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

## 8. Quay video có thuyết minh (OBS)

Nguyên tắc: chuẩn bị trước để bớt thời gian chờ, và khi dựng chỉ **rút gọn** đoạn chờ kèm ghi chú
thời gian thật, không giấu nó. Video là sản phẩm của đồ án nên phải trung thực về tốc độ.

### 8.1. Trước khi bấm quay

- Khởi động đủ hệ thống theo mục 3, kể cả bước làm nóng tìm kiếm (lần tìm đầu sau khi khởi động API
  mất ~30 giây; sau đó ảnh ~1–2 giây, văn bản/thuộc tính ~0,1 giây).
- Dữ liệu ở mốc: nếu vừa diễn tập thì chạy `demo-reset.ps1` (mục 6) rồi khởi động lại API, worker.
- Đóng trình duyệt nhiều tab, IDE và ứng dụng không cần thiết (khi đang xử lý, máy dùng gần hết 16 GB
  RAM); cắm sạc, chọn chế độ hiệu năng cao.
- Trình duyệt phóng to 110–125% để chữ đọc được trong video.

### 8.2. Thứ tự quay

Sắp theo thứ tự này để phần tìm kiếm chạy khi worker còn rảnh (worker xử lý RTSP làm tìm bằng ảnh chậm
lên ~8 giây), và để phần đổi mô hình ở cuối:

1. **Giám sát viên:** các bước B1–B7 ở mục 4 (tìm bằng ảnh, văn bản, văn bản rồi đến ảnh, thuộc tính;
   tạo vụ việc và đánh dấu hoàn thành).
2. **Quản lý:** các bước C1–C2 (dashboard, hồ sơ vụ việc).
3. **Quản trị viên:**
   1. A1–A3: thêm camera RTSP, kiểm tra kết nối, bật AI, xem worker tự tạo phiên.
   2. **Kiểm tra AI** → chọn camera vừa thêm (hoặc `RTSP Cam 1`) → chạy kiểm tra.
   3. **Mô hình AI** → chọn BoT-SORT → **Áp dụng cấu hình**.
   4. D: tắt AI cho camera vừa thêm.
4. Dừng quay, tắt API và worker, chạy `demo-reset.ps1` để đưa dữ liệu và cấu hình mô hình (về
   YOLO11n + ByteTrack) về mốc.

### 8.3. Các đoạn chờ và cách dựng

| Chức năng | Thời gian chờ | Vì sao | Lời nói gợi ý |
| --- | --- | --- | --- |
| Áp dụng đổi mô hình | vài chục giây (chưa đo chính xác) | Hệ thống nạp thử Detector, Tracker, RaSa trước khi lưu | "Hệ thống nạp thử cả bộ mô hình trước khi áp dụng, để không đưa vào vận hành một cặp mô hình lỗi." |
| Kiểm tra AI | vài chục giây (chưa đo chính xác) | Nạp mô hình, đọc khung hình, chạy thử từng bước | "Kiểm tra đi qua đúng các bước của pipeline thật và báo thời gian từng bước." |
| Worker tự tạo phiên RTSP | 13–24 giây | Worker kiểm tra hàng đợi theo chu kỳ | "Không cần thao tác: worker tự nhận camera vừa bật AI." |
| Tìm bằng ảnh lần đầu | ~30 giây | Nạp encoder RaSa | Tránh bằng bước làm nóng ở 8.1 |

Cách dựng mỗi đoạn chờ (Clipchamp có sẵn trên Windows 11, hoặc Shotcut/DaVinci Resolve):

1. Giữ 2–3 giây đầu (thấy "Đang áp dụng…" hoặc vòng xoay).
2. Cắt phần giữa, **hoặc** tua nhanh ×4–×8 và đặt chữ "×8" ở góc.
3. Giữ khoảnh khắc ra kết quả và dừng lâu ở màn hình kết quả (nhãn "Đang dùng" chuyển sang BoT-SORT;
   bảng từng bước Nguồn khung hình → Detector → Tracker → Encoder của Kiểm tra AI; camera "Đang xử lý").
4. Nếu cắt, chèn chữ nhỏ ở góc, ví dụ *(rút gọn — thực tế 40 giây)*, ghi đúng thời gian đã đo khi quay.

### 8.4. Cấu hình OBS gợi ý

- Nguồn: *Window Capture* cửa sổ trình duyệt (không quay cả màn hình để tránh lộ thông báo, ứng dụng
  khác).
- Video: 1920×1080, 30 fps. Ghi ra **MKV** (an toàn nếu OBS tắt đột ngột), sau đó *File → Remux
  Recordings* sang MP4. Chất lượng CQP/CRF khoảng 20–23.
- Quay liên tục, cắt khi dựng; không dùng nút tạm dừng của OBS để bỏ đoạn chờ (video nhảy cóc và mất
  thời gian thật).
