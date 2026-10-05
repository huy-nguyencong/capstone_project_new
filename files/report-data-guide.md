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
| C8.4 | **Hiện hành (05/10/2026, cấu hình đang dùng: ngưỡng 0,1, ByteTrack, RaSa, gallery 1.526 track, 26 truy vấn).** Ảnh→ảnh R@4 0,846, R@8/12/16 0,885, MRR 0,671 (R@8 khoảng tin cậy Wilson 95%: 0,71–0,96); văn bản→ảnh R@4/8 0, R@12/16 0,038, MRR 0,021 (R@8 CI 0–0,13); thuộc tính→ảnh R@4–12 0, R@16 0,038, MRR 0,015 (0–0,13). Hạng kết quả đúng đầu tiên: ảnh median 1 (3 truy vấn thất bại ở hạng 99, 109, 553); văn bản median 73; thuộc tính median 111. Đo với tokenizer gốc của RaSa (sửa ở B1, 05/10); lần chạy cùng ngày với tokenizer chuẩn của Transformers (có [SEP]): văn bản R@8 0,038, MRR 0,021, thuộc tính R@16 0, MRR 0,013, tức là trong nhiễu | Hiện hành | `backend/var/evaluation/wildtrack-v2-conf010-rasatok.json` (bản cuối), `wildtrack-v2-conf010.json` (trước sửa tokenizer), bộ truy vấn `files/wildtrack_evaluation_queries_v2.json` (6 cũ + 20 mới), cache gallery `wildtrack-gallery-conf010.json` |
| C8.4 | Lần đo cũ (27–29/09, 6 truy vấn): ngưỡng 0,25, gallery 1.552: ảnh R@4 0,833, R@8 1,0, MRR 0,867; văn bản và thuộc tính R@4–16 = 0. Ngưỡng 0,1 chỉ đo thuộc tính (R 0, hạng đúng đầu tiên 87/241/365) | **Cũ**, chỉ dùng để nói "cùng bức tranh" | `wildtrack-full.json`, `wildtrack-attributes-v2.json` |
| C8.4 | Phát hiện người ở ngưỡng 0,1 trên 2.800 frame có nhãn, IoU 0,5: precision 0,433 / recall 0,637 (TP 27.194, FP 35.602, FN 15.527); ngưỡng 0,25 (lần cũ): 0,58 / 0,54. Tracking: 1.526 track, 491 không khớp người có nhãn; 825/1.639 người có nhãn được ít nhất một track phủ | Hiện hành | `wildtrack-v2-conf010.json` totals |
| C8.4 | Bộ truy vấn v2: 20 identity mới chọn trong số người xuất hiện trên cả 7 camera với ≥ 30 box cao > 120 px; mô tả và thuộc tính viết từ 3 crop trên 3 camera khác nhau, chỉ dùng từ vựng thuộc tính của ứng dụng; bỏ 63 và 161 vì đi cạnh người mặc giống hệt; ảnh truy vấn là box cao nhất nằm trọn trong khung | Hiện hành | `files/wildtrack_evaluation_queries_v2.json`, `selection_policy` |
| C8.4 | **Chẩn đoán vector (B2, 05/10/2026)**, chỉ vector, 26 truy vấn: crop pipeline cao median 243 px (p10 134, p90 580), 1.100/1.526 thấp hơn 384 px, 122 thấp hơn 128 px, tỉ lệ rộng/cao median 0,38 (huấn luyện 0,33). Cùng khung, box nhãn tay (947 track): văn bản R@16 0,038 → 0,192, median 73 → 67. Gallery nhãn crop cao nhất mỗi người mỗi camera (1.439 crop, 266 người): văn bản R@8 0,115, R@16 0,192, median 107. Cosine truy vấn văn bản với gallery: trung bình 0,19, độ lệch chuẩn 0,04, track đúng 0,21, top-1 0,30. Sáu truy vấn màu đơn: top-16 trùng nhau Jaccard trung bình 0,30, 47 track riêng biệt trên 96 chỗ; "red top" không có áo đỏ nào trong top 16 | Hiện hành | `backend/var/evaluation/wildtrack-text-diagnostics.json`, ảnh ghép `var/evaluation/color-queries/*.png`; công cụ `wildtrack_text_diagnostics.py` |
| C8.4 | **Xếp hạng lại bằng đầu ITM (B5, 05/10/2026)**, cùng gallery và 26 truy vấn, top-N ứng viên của vector search: văn bản N=32 R@8 0.115, N=64 R@8 0.308, N=128 R@4/8/12/16 0.346/0.423/0.462/0.500 MRR 0.329 (R@8 CI 0.26–0.61, hạng đúng đầu tiên median 18); thuộc tính N=128 R@4/8/16 0.115/0.154/0.269 MRR 0.116. Người đúng nằm trong top-16/64/128 của vector: văn bản 1/13/19 trên 26, thuộc tính 1/10/15. ITM 0.19 s mỗi ứng viên trên CPU | Hiện hành | `backend/var/evaluation/wildtrack-v2-conf010-rerank.json`, token cache `wildtrack-gallery-conf010-tokens.npy`; công cụ `evaluate_wildtrack_rerank.py` |
| C8.4 | **CLIP trên cùng gallery và truy vấn (B4, 05/10/2026)**, chỉ vector, open_clip ViT-B/16 laion2b_s34b_b88k, ~0,15 s mỗi crop CPU: ảnh R@4/8/16 0.231/0.346/0.423 MRR 0.195; văn bản R@4/8/16 0.308/0.346/0.500 MRR 0.237 (R@8 CI 0.19–0.54); thuộc tính R@4/8/16 0.154/0.269/0.462 MRR 0.133. Tiền tố "a photo of" đổi tối đa một truy vấn. CLIP ViT-L/14 (laion2b_s32b_b82k): ảnh R@8 0.423, văn bản R@8 0.423, thuộc tính R@8 0.346. So RaSa: ảnh 0,885 / văn bản 0 / thuộc tính 0 (vector), văn bản 0,423 / thuộc tính 0,154 (ITM N=128) | Hiện hành | `backend/var/evaluation/wildtrack-v2-conf010-clip-vit-b16.json` (và `-clip-vit-l14.json` nếu có); công cụ `evaluate_wildtrack_clip.py` |
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
| C8.7 | Độ trễ khi bật xếp hạng lại ITM (05/10/2026, k = 8, 10 lượt mỗi hình thức, cache token của 1.523 track đã có, worker rảnh): N=64: văn bản p50 9,383 ms, p95 10,220 ms; thuộc tính p50 9,073 ms. N=128: văn bản p50 17,034 ms, p95 19,747 ms; thuộc tính p50 17,110 ms. Ảnh không đổi (~1.100 ms). Lần đầu chưa cache: thêm ~1,3 s mỗi ứng viên; warm-up toàn bộ demo 1.523 track mất 49 phút (`tools/warm_itm_cache.py`), cache 1,4 GB | Hiện hành | `backend/var/benchmark/search-latency-rerank64.json`, `search-latency-rerank128.json` |
| C8.7 | Tìm bằng ảnh chậm hơn vì phải mã hóa ảnh bằng RaSa Image Encoder trên CPU; văn bản/thuộc tính chỉ qua Text Encoder. Thời gian ~8 s ở dòng trên đo khi worker đang chạy phiên RTSP và tính cả hiển thị giao diện | Hiện hành | như trên, R7 |
| C8.7 | Dung lượng: ảnh khung trung bình ~358 KB/track (JPEG full frame); vector 256 × 4 byte = 1 KB; database ~24 MB | Hiện hành | truy vấn `frame_size_bytes`, 2026-09-29 |
| C8.7 | RAM theo thành phần (MiB, giá trị lớn nhất trong mỗi trạng thái; stack như khi demo). Hai lần đo: **29/09** (mã gốc, Vite dev server) và **05/10** (sau A1 nạp chọn lọc checkpoint RaSa, A4 API phục vụ `frontend/dist`). **Rảnh sau làm nóng:** container 515 → 363; API 1.978 → 1.134; worker 338 → 300; Vite 318 → 0; FFmpeg 286 → 286; tổng tiến trình ứng dụng 3.435 → 2.083. **Đang tìm kiếm:** API 2.037 → 1.173; tổng 3.430 → 2.250. **Đang xử lý một job:** pipeline AI đỉnh 4.772 → 2.098 (tiến trình chính 728 + tiến trình con 1.370); tổng 7.921 → 4.332 ≈ 4,2 GiB. Máy ảo Docker tính riêng: 828 (29/09, VM chạy lâu) / 3.184 ngay sau khởi động lại (05/10) / 1.686 sau 40 phút | Hiện hành | `backend/var/benchmark/stack-memory-before.json`, `stack-memory-after.json`, `stack-memory-processing-proxy-run.json`, `stack-memory-processing-proxy-run-a5.json`, `encoder-memory-before.json`, `encoder-memory-after-a1.json` (2026-10-05); công cụ `measure_stack_memory.py`, `measure_encoder_memory.py` |
| C8.7 | Điều kiện đo RAM: (1) trạng thái "đang xử lý" dùng `benchmark_sampling.py` chạy đúng pipeline production (YOLO11n 0,1 + ByteTrack + RaSa) trên clip 10 giây thay cho worker, để không ghi track vào dữ liệu demo; worker thật vẫn rảnh và được tính riêng; (2) lấy mẫu mỗi 5 s của công cụ đo stack chỉ bắt được 3.313 (29/09) và 1.936 (05/10) MiB cho pipeline, giá trị đỉnh 4.772 và 2.098 MiB lấy từ bộ lấy mẫu 0,25 s trong benchmark (đỉnh tiến trình chính và con có thể không trùng thời điểm nên là cận trên); (3) RSS trên Windows là working set, bị hệ điều hành cắt bớt khi RAM gần cạn; (4) các ứng dụng khác đang mở nên RAM đã dùng của cả máy là 13,2 → 13,9 → 15,2 GiB (29/09) và 13,7 → 14,5 → 15,1 GiB (05/10) trên 15,7 GiB; (5) số của máy ảo Docker chủ yếu là page cache Linux bên trong VM và phụ thuộc thời gian VM đã chạy; `.wslconfig` giới hạn 3 GB chỉ chặn trần, không làm nhỏ lại | Ghi chú bắt buộc khi trích | như trên |
| C8.7 | Nhận xét R8 (cập nhật 05/10): trước A1, API và pipeline mỗi bên nạp mô hình riêng (API ~1,8 GiB; pipeline đỉnh ~4,2 GiB) vì checkpoint RaSa là checkpoint huấn luyện (1.911 MiB, gồm bản momentum và hàng đợi) và được khởi tạo ngẫu nhiên trước khi chép; sau A1 mỗi bản encoder còn ~0,9 GiB ổn định, đỉnh ~1,0 GiB, vector không đổi. Phần còn lại lớn nhất là hai bản encoder truy vấn (API và worker), xem task A2 trong `part1-improvement-plan.md` | Hiện hành | `encoder-memory-before.json`, `encoder-memory-after-a1.json`, `rasa-equivalence.json` |

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
| C8.4 | Recall ảnh/văn bản ở ngưỡng 0,1 | Đã đo 05/10/2026 với 26 truy vấn (xem dòng C8.4 hiện hành ở trên) | — | Xong |

Nếu không kịp đo, dùng số "Cũ" kèm câu nêu điều kiện, ví dụ: "Số liệu đo với ngưỡng tin cậy 0,25,
trước khi hạ xuống 0,1; thời gian và số track ở cấu hình hiện tại có thể khác."
