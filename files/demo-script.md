# Kịch bản demo PRISM

> Tài liệu thực hiện cho buổi bảo vệ (R7 trong `remaining-work-plan.md`); không phải nguồn yêu cầu.
> Luồng trình diễn bám theo architect §1/§10: Quản trị viên thiết lập camera RTSP, hệ thống tự xử lý,
> Giám sát viên tìm kiếm và lưu vụ việc, Quản lý theo dõi.

## 1. Tóm tắt

| Phần | Vai trò | Nội dung | Thời gian thao tác |
| --- | --- | --- | --- |
| A | Quản trị viên | Thêm camera RTSP, kiểm tra kết nối, bật AI, xem worker tự tạo phiên | ~40 giây |
| B | Giám sát viên | Tìm bằng ảnh, mở kết quả, tạo vụ việc và đánh dấu hoàn thành | ~25 giây |
| C | Quản lý | Dashboard, mở hồ sơ vụ việc | ~15 giây |
| D | Quản trị viên | Tắt AI cho camera vừa thêm | ~10 giây |

Thời gian thao tác đo khi diễn tập tự động (2026-09-28, hai lần liên tiếp đều đạt): 85–88 giây chưa kể
lời thuyết minh. Khi trình bày có lời nói, dự kiến 6–8 phút.

Dữ liệu demo: 7 camera WILDTRACK (khu vực Gate A), 1.488 track trong 2 phút đầu của mỗi video, cùng
camera `RTSP Cam 1` (35 track) và 1 vụ việc có sẵn ("Tìm người để quên hành lý", 3 kết quả); tổng
1.523 track. Mốc dữ liệu: `backups/20260928T184653Z` (đã verify, đã thử `demo-reset.ps1`).

## 2. Chuẩn bị trước ngày bảo vệ

- [ ] Máy cắm sạc, tắt chế độ ngủ; đóng trình duyệt/IDE không cần thiết (RAM máy 16 GB chỉ còn ~2 GB
      trống khi chạy đủ stack).
- [ ] Chạy trọn kịch bản ít nhất một lần bằng tay trên chính máy demo; sau đó đưa dữ liệu về mốc
      (mục 6).
- [ ] Quay video màn hình có thuyết minh làm phương án dự phòng. Bản dự phòng không lời do diễn tập tự
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
| B5 | Đăng xuất | | |

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
