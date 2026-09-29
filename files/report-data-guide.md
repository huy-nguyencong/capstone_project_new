# Hướng dẫn lấy số liệu cho báo cáo (Chương 7, 8, 9)

> Tài liệu thực hiện, viết cho session viết báo cáo. Không phải nguồn yêu cầu; ba đặc tả trong
> `files/` vẫn là nguồn chính. Cập nhật lần cuối 2026-09-29 (thêm đo benchmark, độ trễ, RAM). Khi số liệu mới được đo, cập nhật bảng
> ở mục 3 và ghi ngày.

## 1. Quy tắc

1. **Mỗi con số trong báo cáo phải có:** cấu hình (mô hình, ngưỡng, N), dữ liệu (tập nào, bao nhiêu
   track/video), máy đo, số lần chạy, ngày đo. Không có đủ thì chưa được dùng.
2. **Chỉ dùng số trong bảng ở mục 3, theo đúng cột "Trạng thái":**
   - **Hiện hành**: đo trên cấu hình đang chạy (mục 2). Dùng trực tiếp.
   - **Cũ**: đo với cấu hình khác (thường là ngưỡng Detector 0,25). Chỉ dùng kèm câu ghi rõ điều kiện
     đo, hoặc đề nghị sinh viên đo lại (mục 4). Không trộn với số hiện hành trong cùng một bảng mà
     không ghi chú.
   - **Chưa đo**: không ước lượng, không suy ra từ số khác. Viết phương pháp đo và để trống/ghi "chưa
     đo", hoặc chuyển thành hạn chế.
3. **Không tự chạy phép đo.** Session viết báo cáo chỉ sửa báo cáo và ba file đặc tả. Nhiều phép đo
   ghi dữ liệu (lập chỉ mục, E2E, diễn tập demo) hoặc chạy hàng giờ; khi cần đo, ghi yêu cầu cho sinh
   viên theo mục 4.
4. **Không lấy số từ database đang chạy.** Database demo thay đổi khi sinh viên thử hệ thống (ví dụ
   bật AI cho camera RTSP làm tăng số track). Số lượng dữ liệu demo lấy từ mục 3, là số của mốc
   `backups/20260928T184653Z`.
5. **Không so sánh Recall giữa hai tập khác nhau.** Tập đánh giá (gallery từ toàn bộ video,
   AIW-26) khác tập dữ liệu demo (0–120 giây). Truy vấn demo chỉ là kiểm tra định tính.
6. Nguồn chi tiết: `architect.md` §13 (kết quả đo đã chốt), `ai_worker_implementation_plan.md`
   §12 (nhật ký AIW-24..29), `remaining-work-plan.md` mục R1–R8 và mục 6, `demo-script.md`.

## 2. Cấu hình hiện hành

| Thành phần | Giá trị |
| --- | --- |
| Máy | Intel Core i5-11300H (4 nhân/8 luồng, 3,1 GHz), RAM 16 GB, không GPU rời, Windows 11 |
| Detector | YOLO11n (COCO), ngưỡng tin cậy **0,1** (hạ từ 0,25 ngày 2026-09-27) |
| Tracker | ByteTrack (`bytetrack_v1`); BoT-SORT đã tích hợp nhưng chưa dùng để lập chỉ mục hay đo |
| Encoder | RaSa CUHK-PEDES, vector 256 chiều, metric IP |
| Lấy mẫu | Profile `throughput`, N=20 (1 khung trên 20 khung nguồn) |
| Dữ liệu demo | 7 camera WILDTRACK, đoạn 0–120 giây mỗi camera, **1.488 track**; cộng camera `RTSP Cam 1` (35 track) → **1.523 track**; 1 vụ việc có sẵn (3 kết quả) |

## 3. Số liệu theo mục báo cáo

### C7 — Triển khai

| Mục | Số liệu | Trạng thái | Nguồn |
| --- | --- | --- | --- |
| C7.2 | Lập chỉ mục đoạn 60–120 giây: 7 job, 55 phút, +752 track, 0 lỗi; đoạn 0–60 giây trước đó 736 track | Hiện hành | `remaining-work-plan.md` R6 |
| C7.2 | Track theo camera (0–120 giây): C1 208, C2 254, C3 308, C4 188, C5 182, C6 159, C7 189 | Hiện hành | R6 |
| C7.2 | Công cụ: `backend/tools/index_wildtrack.py` qua API (đường tải video), 7 camera cùng một mốc thời gian gốc | Hiện hành | R6 |
| C7.2 | CPU chậm hơn thời gian thực ~7 lần nên dữ liệu demo lập chỉ mục từ tệp video; RTSP dùng để trình diễn | Hiện hành | architect §13 #1, #7 |
| C7.3 | Sao lưu dữ liệu demo: ~510 MB, 1.525 tệp (1.523 ảnh + dump + manifest) | Hiện hành | R7 (mốc mới) |
| C7.3 | Khôi phục đầy đủ (1.555 track, có 10 ảnh bị xóa để thử): **28,8 giây**, exit 0 (PostgreSQL 1,8 s; ảnh 6,2 s, upload lại 10/10; reindex Milvus 8,8 s; reconcile 12 s) | Hiện hành | R6; STO-19 trong `storage_database_implementation_plan.md` |
| C7.3 | Trước khi tối ưu reindex theo lô: 1.485 s, 1 vector timeout — có thể nêu như một phát hiện nhờ diễn tập | Hiện hành | R6 |
| C7.3 | Đưa dữ liệu về mốc sau diễn tập (`scripts/demo-reset.ps1`): ~70 giây | Hiện hành | R7 |

### C8 — Kiểm thử và đánh giá

| Mục | Số liệu | Trạng thái | Nguồn |
| --- | --- | --- | --- |
| C8.1–C8.2 | Unit (gồm contract, security, failure injection): **713 pass** | Hiện hành | 2026-09-29, commit `b3a6889` + thay đổi đo tài nguyên trong `evaluation/benchmark.py` |
| C8.2 | Integration (database dùng một lần, R3): kết nối storage 2 pass + 1 skip (failure injection cần tắt dịch vụ); dịch vụ dùng DSN riêng 21; adapter 4; migration/schema 7; RTSP/MediaMTX 3 | Hiện hành | R3 |
| C8.2 | E2E: 2 pass; luồng AI thật với clip 10 giây mất 217 s (nạp mô hình 44 s, job 154 s, tìm văn bản lần đầu 16 s) | Hiện hành | R3 |
| C8.2 | Giao diện: 20 màn hình × 3 cỡ (390, 768, 1440 px), không tràn, không lỗi console/HTTP; 3 lỗi tìm ra và đã sửa | Hiện hành | R5 |
| C8.2 | Diễn tập kịch bản demo tự động: 2 lần liên tiếp, 15/15 bước, 85–88 giây thao tác | Hiện hành | R7 |
| C8.3 | Phân quyền và bảo mật (nằm trong 711 unit test): mọi route có quy tắc truy cập và ma trận quyền theo vai trò, CSRF cho mọi thao tác ghi, rate limit đăng nhập/tìm kiếm, security header, CORS (`tests/unit/test_hardening.py`); vụ việc của Operator khác trả 404, Viewer chỉ đọc, track ngoài khu vực và ảnh của vụ việc khác bị chặn (`tests/unit/test_cases_api.py`); chặn test chạy nhầm database demo (R2) | Hiện hành | các file test nêu trên, R2 |
| C8.4 | Ảnh→ảnh Recall@4 0,8333, Recall@8/12/16 1,0, MRR 0,8667; văn bản→ảnh Recall@4–16 = 0, MRR 0,01; thuộc tính→ảnh Recall 0, MRR 0,005 | **Cũ**: ngưỡng Detector 0,25, gallery 1.552 track, 6 truy vấn | `backend/var/evaluation/wildtrack-full.json`, architect §13 #3 |
| C8.4 | Thuộc tính→ảnh (bộ thuộc tính mới) Recall@4–16 = 0, MRR 0,0045; kết quả đúng đầu tiên ở hạng 87/241/365 | Hiện hành (ngưỡng 0,1, gallery 1.526 track) | `wildtrack-attributes-v2.json`, architect §13 #3 |
| C8.4 | Phát hiện người: lần 1 precision 0,58 / recall 0,54 (ngưỡng 0,25); lần 2 precision 0,43 / recall 0,64 (ngưỡng 0,1) | Hai lần khác điều kiện, so sánh định tính | architect §13 #5 |
| C8.4 | **Lưu ý:** lần đo 2 chỉ chạy tìm bằng thuộc tính. Recall tìm bằng ảnh và văn bản ở ngưỡng 0,1 **chưa đo**; không ghi "Recall ảnh 0,83 trên 1.526 track" | — | — |
| C8.4 | Kiểm tra định tính trên dữ liệu demo (tìm bằng ảnh, top 8, xem bằng mắt): Q006 8/8, Q002 8/8, Q001 8/8, Q004 7/8, Q003 4/8; kết quả đúng nằm trên 4–5 camera | Hiện hành, định tính | R6, `demo-script.md` |
| C8.5 | N=10 so với N=20 (clip 10 giây, 3 lượt/N): thời gian khi đã nạp mô hình 133,9 s so với 105,8 s; 46 so với 36 track; track ngắn 26 so với 25; ảnh đại diện 12,0 MB so với 6,55 MB | **Cũ**, đã thay bằng các dòng dưới: ngưỡng 0,25; không có RAM đỉnh; CPU chỉ tính tiến trình chính | `backend/var/benchmark/local-cpu-demo.json`, AIW-27 |
| C8.5 | N=10 so với N=20, ngưỡng 0,1 (clip `cam1-demo-10s.mp4` 600 khung, 3 lượt/N xen kẽ, lượt đầu N=10 là cold): thời gian khi mô hình đã nạp (warm) **149,5 s** [136,6–162,4; 2 lượt] so với **132,6 s** [118,3–143,4; 3 lượt] (N=20 bằng 91% N=10); số track 44 so với 36; track ngắn (< 2 s) 22 so với 24; ảnh đại diện 10,2 MB so với 6,9 MB; cold N=10 178,5 s | Hiện hành | `backend/var/benchmark/local-cpu-demo-conf010.json` (2026-09-29, commit `b3a6889`) |
| C8.5 | Tài nguyên theo N (cùng lần đo): CPU warm (tiến trình chính + tiến trình con mô hình) ~212 s so với ~160 s; peak RSS tiến trình chính ≤ 695 so với ≤ 576 MiB, tổng tiến trình con (Detector, Encoder) ≤ 4.284 so với ≤ 4.267 MiB | Hiện hành; lấy mẫu psutil mỗi 0,25 s nên là giá trị dưới | như trên, `peak_rss_bytes_*`, `cpu_seconds_*` |
| C8.5 | Giải thích: thời gian mỗi lượt chủ yếu do Image Encoder (~1,85 s/track, trung bình trên lượt warm) nhân số track và thời gian nạp mô hình (~6–7 s); Detector chỉ ~0,16–0,23 s/khung lấy mẫu. N=20 bớt một nửa số khung chạy Detector và bớt ~8 track, nên chỉ nhanh hơn ~9% | Hiện hành | `stage_mean_ms` trong tệp trên |
| C8.5 | Điều kiện đo: máy không đóng ứng dụng khác (IDE, trình duyệt), tải nền không kiểm soát; độ dao động giữa các lượt ±12 s. Python 3.13.2 (lần cũ 3.12.10) | Ghi chú bắt buộc khi trích | như trên |
| C8.6 | RTSP: chạy bình thường 300 frame/29 track, tìm văn bản 8 kết quả, 136 s; ngắt publisher 5 s → reconnect 1 lần, 600 frame/38 track, 140 s; tắt AI giữa phiên → `CANCELLED`, 0 track dở dang | **Cũ** về số track (ngưỡng 0,25); kết luận chức năng vẫn đúng | AIW-28 |
| C8.6 | Diễn tập demo: camera RTSP mới "Trực tuyến", worker tự tạo phiên sau 13–24 s | Hiện hành | R7 |
| C8.7 | Tìm bằng ảnh qua giao diện: lần đầu sau khởi động API ~31 s (nạp encoder); sau đó ~8 s khi worker đang xử lý RTSP; không làm nóng + worker bận: ~97 s | Hiện hành, đo từng lần, chưa phải p50/p95 | R7 |
| C8.7 | Độ trễ tìm kiếm phía client qua API (k = 8, 30 lượt mỗi hình thức sau 1 lượt làm nóng, gọi xen kẽ cách 2,5 s, worker rảnh, dữ liệu demo 1.523 track): **ảnh** p50 1.269 ms, p95 1.976 ms, max 2.289 ms; **văn bản** p50 106 ms, p95 142 ms, max 151 ms; **thuộc tính** p50 103 ms, p95 136 ms, max 136 ms; 0 lượt bị 429 | Hiện hành | `backend/var/benchmark/search-latency-conf010.json` (2026-09-29), công cụ `backend/tools/benchmark_search_latency.py` |
| C8.7 | Tìm bằng ảnh chậm hơn vì phải mã hóa ảnh bằng RaSa Image Encoder trên CPU; văn bản/thuộc tính chỉ qua Text Encoder. Thời gian ~8 s ở dòng trên đo khi worker đang chạy phiên RTSP và tính cả hiển thị giao diện | Hiện hành | như trên, R7 |
| C8.7 | Dung lượng: ảnh khung trung bình ~358 KB/track (JPEG full frame); vector 256 × 4 byte = 1 KB; database ~24 MB | Hiện hành | truy vấn `frame_size_bytes`, 2026-09-29 |
| C8.7 | RAM theo thành phần (giá trị lớn nhất trong mỗi trạng thái; stack như khi demo: PostgreSQL, Milvus + etcd, MinIO, MediaMTX + 7 luồng FFmpeg, API, worker, Vite). Đơn vị MiB. **Rảnh, sau khi làm nóng:** container 515 (máy ảo Docker 828), API 1.978 (gồm encoder truy vấn; trước khi làm nóng 153), worker 338, Vite 318, FFmpeg 286 → ứng dụng (máy ảo Docker + tiến trình) ~3.750 MiB ≈ 3,7 GiB. **Đang tìm kiếm:** API 2.037, các thành phần khác như lúc rảnh. **Đang xử lý một job:** thêm pipeline AI ≤ 4.772 MiB lúc đỉnh (tiến trình chính 675 + tiến trình con 4.097, lượt N=10) → ứng dụng ~8.200 MiB ≈ 8,0 GiB | Hiện hành | `backend/var/benchmark/stack-memory.json`, `stack-memory-processing-proxy-run.json` (2026-09-29); công cụ `backend/tools/measure_stack_memory.py` |
| C8.7 | Điều kiện đo RAM: (1) trạng thái "đang xử lý" dùng `benchmark_sampling.py` chạy đúng pipeline production (YOLO11n 0,1 + ByteTrack + RaSa) trên clip 10 giây thay cho worker, để không ghi track vào dữ liệu demo; worker thật vẫn rảnh và được tính riêng; (2) lấy mẫu mỗi 5 s của công cụ đo stack chỉ bắt được 3.313 MiB cho pipeline, giá trị đỉnh 4.772 MiB lấy từ bộ lấy mẫu 0,25 s trong benchmark (đỉnh tiến trình chính và con có thể không trùng thời điểm nên là cận trên); (3) RSS trên Windows là working set, bị hệ điều hành cắt bớt khi RAM gần cạn; (4) các ứng dụng khác đang mở nên RAM đã dùng của cả máy là 13,2 GiB (rảnh, trước làm nóng) → 13,9 GiB (sau làm nóng, khi tìm kiếm) → 15,2 GiB (đang xử lý) trên 15,7 GiB | Ghi chú bắt buộc khi trích | như trên |
| C8.7 | Nhận xét R8: API và pipeline mỗi bên nạp mô hình riêng (API ~1,8 GiB cho encoder truy vấn; pipeline ~4,2 GiB cho Detector và Image Encoder); khi chạy song song trên máy 16 GB có mở ứng dụng khác thì gần hết RAM. Khi demo nên đóng ứng dụng không cần thiết; chưa cần tách encoder truy vấn thành tiến trình riêng | Hiện hành (đánh giá) | như trên |

### C9 — Tổng kết

Hạn chế đã có căn cứ: tìm bằng văn bản/thuộc tính Recall thấp trên WILDTRACK (C8.4); CPU chậm hơn
thời gian thực ~7 lần, xử lý tuần tự từng camera (architect §13 #1); mốc thời gian RTSP lấy theo đồng hồ
lúc đọc nên track RTSP dễ bị tách (architect §13 #7); lần tìm đầu chậm do nạp encoder (C8.7). Hướng
phát triển có căn cứ: xếp hạng lại image–text của RaSa, tinh chỉnh trên dữ liệu cùng miền, OpenVINO
(R10), đánh giá BoT-SORT.

## 4. Các phép đo còn thiếu

Khi báo cáo cần một số liệu "Cũ" hoặc "Chưa đo", ghi yêu cầu cho sinh viên. Phép đo do sinh viên
(hoặc session phát triển) chạy, không phải session viết báo cáo.

| Cần cho | Việc đo | Lệnh / cách làm | Thời gian | Ghi dữ liệu demo? |
| --- | --- | --- | --- | --- |
| C8.4 | Recall ảnh/văn bản ở ngưỡng 0,1 | `python tools/evaluate_wildtrack.py ...` như AIW-26 (`ai_worker_implementation_plan.md` §12.4, dòng 11) | Nhiều giờ (chạy pipeline trên 7 video) | Không (ghi ra `var/evaluation`) |

Nếu không kịp đo, dùng số "Cũ" kèm câu nêu điều kiện, ví dụ: "Số liệu đo với ngưỡng tin cậy 0,25,
trước khi hạ xuống 0,1; thời gian và số track ở cấu hình hiện tại có thể khác."
