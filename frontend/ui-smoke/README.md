# Kiểm thử hồi quy giao diện

Hai kịch bản Playwright chạy trên trình duyệt Microsoft Edge có sẵn (`playwright-core`,
`channel: 'msedge'`), không tải trình duyệt mới. Cần chạy API (`python -m person_search`),
`npm run dev` và các tài khoản seed `admin`, `operator`, `viewer`.

| Lệnh                        | Việc kiểm tra                                                                                                                                                                                                                                                                                                                 | Ghi dữ liệu                                  |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `npm run ui:smoke`          | Đăng nhập từng vai trò, mở mọi trang ở 390×844 (điện thoại), 768×1024 (máy tính bảng), 1440×900 (máy tính); chụp toàn trang; báo phần tử tràn ngang, lỗi console/trang và response HTTP lỗi; thử tìm bằng văn bản, mở kết quả, hộp thoại tạo vụ việc (hủy), bộ chọn thuộc tính và chọn thẻ ở trang Mô hình AI (không áp dụng) | Không                                        |
| `npm run ui:smoke -- phone` | Như trên, chỉ một cỡ (`phone`, `tablet`, `desktop`)                                                                                                                                                                                                                                                                           | Không                                        |
| `npm run ui:case-status`    | Bộ lọc trạng thái trang Vụ việc: tab Hoàn thành không giữ chi tiết cũ; đóng rồi mở lại vụ việc `OPEN` đầu tiên và kiểm tra nó chuyển đúng tab                                                                                                                                                                                 | Có: vụ việc trở về `OPEN`, thêm 2 dòng audit |

`npm run ui:demo` (cần `DEMO_RTSP_URL=rtsp://<IP-LAN>:8554/cam2`) chạy trọn kịch bản demo trong
`files/demo-script.md` ở 1440×900 và quay video `output/demo/<thời điểm>/demo.webm`; có ghi dữ liệu
(camera, vụ việc, phiên RTSP) nên chạy trên mốc dữ liệu rồi `scripts/demo-reset.ps1`. Quay video cần
bản ffmpeg của Playwright: `npx playwright-core install ffmpeg` (một lần).

Ảnh chụp và `report.json` nằm trong `ui-smoke/output/<cỡ>/` (đã gitignore). Lệnh trả exit code 1
khi có màn hình bị đánh dấu. Số đo tự động không thay cho việc xem ảnh: sau mỗi đợt sửa giao diện
cần mở ảnh của các trang liên quan ở cả ba cỡ.

Biến môi trường: `UI_SMOKE_BASE` (mặc định `http://localhost:5173`), `UI_SMOKE_PASSWORD` (mặc
định `password`, mật khẩu seed phát triển).

Lần tìm kiếm đầu sau khi khởi động API phải nạp encoder RaSa (15–45 giây trên CPU); kịch bản chờ
tối đa 60 giây, giao diện đặt timeout riêng 120 giây cho request tìm kiếm.
