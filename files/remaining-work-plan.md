# Kế hoạch hoàn thiện phần ứng dụng PRISM

> Lập ngày 2026-09-28. Tài liệu kế hoạch thực hiện, **không phải nguồn yêu cầu** và không ghi đè ba
> tài liệu nguồn `project_requirements.md`, `usecase_detail.md`, `architect.md` (cùng thư mục
> `files/`); khi có mâu thuẫn, sửa tài liệu này theo tài liệu nguồn. Thư mục `docs/` cũ đã được gỡ
> khỏi repo ngày 2026-09-28. Kế hoạch viết báo cáo nằm riêng ở `report/report_plan.md`; tài liệu
> này chỉ nhắc tới báo cáo ở những chỗ hai bên phụ thuộc nhau.

## 1. Tình trạng hiện tại

Các chức năng trong ba tài liệu đặc tả đã được hiện thực và kiểm chứng trên dữ liệu thật:

- Ba vai trò (Quản trị viên, Giám sát viên, Quản lý) với đủ UC-01 → UC-15, gồm đưa camera vận hành trở
  lại, trạng thái vụ việc (Đang xử lý/Hoàn thành) và đánh dấu hoàn thành khi lưu.
- Pipeline RTSP/tệp video → lấy mẫu `N=20` → YOLO11n → ByteTrack hoặc BoT-SORT → RaSa → ba kho
  (PostgreSQL, Milvus, MinIO) với `PENDING → READY`; worker tự xoay vòng phiên RTSP.
- Tìm kiếm bằng ảnh (kéo thả, dán, kéo kết quả để tìm tiếp), văn bản tiếng Anh, thuộc tính (bộ từ vựng
  mở rộng, không có phủ định); ảnh kết quả nới theo khung và đánh dấu người được tìm thấy.
- Giao diện tiếng Việt, dùng được trên điện thoại (đã kiểm thử ở 390 px).
- 699 unit test pass; ruff, ESLint, build frontend sạch; 7 camera WILDTRACK đã lập chỉ mục (736 track
  `READY`, 60 giây đầu mỗi camera).

Những việc còn lại dưới đây là **dọn dẹp, đồng bộ, kiểm thử và chuẩn bị demo**, không còn yêu cầu chức
năng nào chưa làm.

## 2. Nguyên tắc khi thực hiện

1. Không thêm chức năng ngoài ba tài liệu đặc tả. Nếu cần thay đổi hành vi, sửa đặc tả trước.
2. Mọi thao tác xóa dữ liệu phải có **chế độ chạy thử (dry-run) mặc định** và **sao lưu trước** bằng
   `backend/tools/storage_backup.py`.
3. Integration test và E2E test chỉ chạy trên **database dùng một lần** (ví dụ `person_search_citest`),
   không bao giờ trỏ vào database `person_search` đang dùng để demo.
4. Số liệu ghi vào báo cáo chỉ lấy từ lần chạy thật, ghi rõ cấu hình máy.
5. Trước khi chạy worker dài: cắm sạc, tắt chế độ ngủ (Settings → Power → Screen and sleep → Never).

## 3. Danh sách công việc

| Mã | Việc | Ưu tiên | Phụ thuộc | Ước lượng | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| R1 | Dọn dữ liệu rác của integration test trong database demo | Cao | — | 0,5 ngày | XONG (2026-09-28) |
| R2 | Chặn integration/E2E test chạy nhầm vào database demo | Cao | — | 1–2 giờ | XONG (2026-09-28) |
| R3 | Chạy lại toàn bộ bộ test (unit, integration, E2E) và sửa lỗi phát sinh | Cao | R2 | 0,5–1 ngày | XONG (2026-09-28) |
| R4 | Đồng bộ ba file kế hoạch triển khai với đặc tả | Trung bình | — | 0,5 ngày | XONG (2026-09-28) |
| R5 | Kiểm thử hồi quy giao diện (máy tính và điện thoại), đưa kịch bản vào repo | Trung bình | R1 | 2–3 giờ | XONG (2026-09-28) |
| R6 | Chuẩn bị dữ liệu demo và đưa script lập chỉ mục vào repo | Cao | R1 | 0,5 ngày + thời gian máy chạy | XONG (2026-09-28) |
| R7 | Kịch bản demo và bằng chứng nhận luồng RTSP | Cao | R6 | 0,5 ngày | XONG (2026-09-28); còn tự diễn tập, quay video có lời |
| R8 | Đo RAM toàn stack (architect §13 mục 4) | Thấp | R6 | 2 giờ | XONG (2026-09-29) |
| R9 | *(Tùy chọn)* Thử xếp hạng lại image–text của RaSa cho tìm bằng văn bản | Thấp | R3 | 1–2 ngày | TÙY CHỌN |
| R10 | *(Tùy chọn)* Thử tăng tốc bằng OpenVINO | Thấp | R8 | 1–2 ngày | TÙY CHỌN |

Thứ tự đề xuất: **R2 → R1 → R6 → R5 → (chụp ảnh chương 6) → R3 → R7 → R4 → R8**; R9, R10 chỉ làm khi
còn thời gian sau khi báo cáo đã xong chương 8.

## 4. Chi tiết từng việc

### R1. Dọn dữ liệu rác của integration test

**Vấn đề.** Integration test từng chạy trỏ vào database demo, để lại khoảng 78 khu vực `A-xxxxxxxx`
(tên hiển thị đều là "Gate A"), khoảng 80 camera tên "Gate Camera", 258 tài khoản dạng
`admin.xxxxxxxx`, `operator.xxxxxxxx`, `viewer.xxxxxxxx`, cùng job, track và audit log liên quan. Trang
Camera, Trạng thái hệ thống và Tài khoản hiện hàng loạt mục trùng tên, không dùng được để chụp ảnh báo
cáo hay demo. Ngoài ra `reconcile` còn báo 25 track `READY` của dữ liệu rác thiếu ảnh/vector, cùng 2
object và 3 vector mồ côi do job Cam 6 bị ngắt.

**Cách làm.** Viết `backend/tools/purge_test_fixtures.py`:

1. Xác định dữ liệu rác theo **dấu hiệu chắc chắn**, không theo tên hiển thị:
   - khu vực có `code` khớp `^A-[0-9A-F]{8}$`;
   - tài khoản có `username` khớp `^(admin|operator|viewer)\.[0-9a-f]{8}$`;
   - camera thuộc các khu vực trên.
   Tuyệt đối không đụng tới `CAMPUS`, `GATE-A`, ba tài khoản seed, camera `WT-CAM1..7`, `RTSP-CAM1`,
   `E2E-*` và hai vụ việc thật.
2. Chế độ mặc định **dry-run**: in số bản ghi sẽ xóa theo từng bảng. Chỉ xóa khi có `--apply`.
3. Xóa theo thứ tự khóa ngoại (đều là `RESTRICT`, trừ các chỗ ghi chú):
   `case_results` của vụ việc thuộc tài khoản rác → `cases` của tài khoản rác →
   `storage_outbox_events` của track rác → object MinIO và vector Milvus của track rác →
   `person_tracks` → `processing_jobs` → `cameras` → `users` (`auth_sessions` tự xóa theo `CASCADE`,
   `audit_logs.actor_user_id` tự thành `NULL` theo `SET NULL`) → `areas`.
4. Audit log **giữ lại** (nhật ký chỉ tra cứu, không sửa), chỉ mất liên kết tới người thực hiện.
5. Sau khi xóa, chạy `person-search-storage reconcile` (dry-run, exit 2 nếu còn sai lệch) để kiểm tra,
   đọc kết quả rồi `person-search-storage reconcile --delete-orphans --actor-user-id <admin-id>` để
   dọn object/vector mồ côi.

**Tiêu chí hoàn thành.**
- Trang Camera chỉ còn các camera thật; bộ lọc khu vực chỉ còn "Campus", "Gate A".
- Trang Tài khoản chỉ còn các tài khoản thật; `reconcile` báo `missing_* = 0`, `orphan_* = 0`.
- Giám sát viên tìm kiếm vẫn ra kết quả như trước; hai vụ việc thật và 736 track WILDTRACK còn nguyên.

**Rủi ro.** Xóa nhầm dữ liệu thật. Giảm thiểu bằng dry-run, sao lưu trước, và kiểm tra lại bằng các
câu truy vấn đếm trước/sau.

**Kết quả (2026-09-28).** Sao lưu trước tại `backups/20260928T141515Z` (đã verify). Công cụ đã xóa 86 khu
vực, 258 tài khoản, 82 camera, 62 job, 25 track và 25 outbox event; kiểm tra an toàn không phát hiện
tham chiếu nào tới dữ liệu thật. Trigger append-only của `audit_logs` chặn bước `SET NULL`, nên công
cụ tắt trigger ngay trong transaction xóa rồi bật lại trước khi commit: 658 dòng audit vẫn còn đủ,
482 dòng của tài khoản rác chỉ mất liên kết người thực hiện. `reconcile --delete-orphans` đã dọn 2 object
và 3 vector mồ côi; `reconcile` chạy lại báo 0 ở mọi mục. Còn lại 2 khu vực, 3 tài khoản, 9 camera,
803 track (736 track WILDTRACK), cùng 2 vụ việc với 5 kết quả.

### R2. Chặn test chạy nhầm vào database demo

**Nguyên nhân gốc của R1.** Các test đọc DSN từ biến môi trường, không có gì ngăn việc trỏ vào database
demo.

**Cách làm.**
1. Thêm một hàm kiểm tra dùng chung trong `backend/tests/conftest.py`: từ chối chạy (`pytest.exit`)
   nếu tên database trong các DSN `PERSON_SEARCH_CAMERA_TEST_DSN`,
   `PERSON_SEARCH_POSTGRES_DSN` (khi bật `PERSON_SEARCH_RUN_MIGRATION_INTEGRATION`,
   `PERSON_SEARCH_RUN_ADAPTER_INTEGRATION`, `PERSON_SEARCH_RUN_E2E`) **không** kết thúc bằng
   `_test` hoặc `_citest`.
2. Thêm script `scripts/test-db.ps1` với hai lệnh `create`/`drop` cho database dùng một lần
   (`person_search_citest`) và in sẵn DSN để export.
3. Cập nhật `backend/tests/integration/README.md` và `backend/tests/e2e/README.md`.

**Tiêu chí hoàn thành.** Chạy integration test với DSN trỏ vào `person_search` bị dừng ngay kèm thông
báo rõ ràng; trỏ vào `person_search_citest` thì chạy bình thường.

**Kết quả (2026-09-28).** Logic kiểm tra nằm ở `backend/tests/database_guard.py`, được gọi trong
`pytest_configure` của `backend/tests/conftest.py`. Môi trường được đọc giống như test thực tế:
`backend/.env`, bị ghi đè bởi biến môi trường. DSN thiếu hoặc không đọc được cũng bị chặn; có 9 unit
test cho logic này. `scripts/test-db.ps1 create` tạo lại `person_search_citest` ở migration head và in
DSN, `drop` xóa database đó. Đã kiểm tra: bật cờ migration mà vẫn dùng DSN demo từ `.env`, hoặc đặt
`PERSON_SEARCH_CAMERA_TEST_DSN` là DSN demo, đều bị dừng với exit 4; trỏ vào `citest` thì 13 test camera
và video job đều pass; unit suite 708 pass. MinIO/Milvus vẫn dùng chung với demo, nhưng test dùng
collection/alias riêng và tự dọn object nên không cần chặn.

### R3. Chạy lại toàn bộ bộ test

Trong đợt sửa gần đây mới chạy unit test (699 pass) và `test_camera_admin.py`. Nhiều thay đổi backend
(trạng thái vụ việc, crop theo tỉ lệ và đánh dấu, BoT-SORT, lập lịch RTSP, bộ thuộc tính mới, chặn bật
AI khi camera mất kết nối) chưa được kiểm lại trên integration/E2E.

**Cách làm** (database tạm từ R2, storage đang chạy):

| Nhóm | Biến môi trường | Ghi chú |
| --- | --- | --- |
| Unit | — | `python -m pytest -m unit --basetemp <thư mục tạm>` (thư mục `%TEMP%\pytest-of-congh` đang bị khóa quyền) |
| Kết nối storage | `PERSON_SEARCH_RUN_INTEGRATION=1` | `test_storage_connections.py` |
| Migration và schema | `PERSON_SEARCH_RUN_MIGRATION_INTEGRATION=1` | Tự chạy `downgrade base → upgrade head`; kiểm tra migration `20260927_0013` (trạng thái vụ việc) |
| Adapter storage | `PERSON_SEARCH_RUN_ADAPTER_INTEGRATION=1` | `test_storage_adapters.py`, `test_storage_read_paths.py`, `test_track_ingestion_flow.py` |
| Dịch vụ dùng DSN riêng | `PERSON_SEARCH_CAMERA_TEST_DSN=<citest>` | camera, video job, worker bền vững, telemetry, diagnostics |
| E2E | `PERSON_SEARCH_RUN_E2E=1` (xem `tests/e2e/conftest.py`) | `test_storage_workflow.py`, `test_ai_worker_slice.py` (dùng mô hình thật, chạy lâu) |

**Tiêu chí hoàn thành.** Tất cả pass; lỗi nào phát sinh do thay đổi gần đây thì sửa code hoặc cập nhật
test theo đặc tả hiện tại, ghi lại trong bảng ở mục 6.

### R4. Đồng bộ ba file kế hoạch triển khai

Theo quy ước ở đầu ba tài liệu nguồn, kế hoạch triển khai phải khớp với đặc tả. Hiện đang lệch:

| File | Nội dung cần cập nhật |
| --- | --- |
| `files/backend_implementation_plan.md` | Bỏ các câu "Case không có trạng thái"; thêm trạng thái vụ việc (`PATCH` nhận `status`, lỗi `409 case_closed`, lọc `?status=`, dashboard đếm theo trạng thái, sự kiện `case.closed`/`case.reopened`); `POST /admin/cameras/{id}/reactivate` và `camera.reactivated`; `409 camera_offline`; API crop `?aspect=&mark=`; chặn truy vấn không phải tiếng Anh `422 text_not_english`; bộ thuộc tính mới |
| `files/storage_database_implementation_plan.md` | Bỏ các câu "không có trạng thái"; migration `20260927_0013` (enum `case_status`, cột `status`, `closed_at`, ràng buộc CHECK, chỉ mục) |
| `files/ai_worker_implementation_plan.md` | BoT-SORT (`botsort_v1`, `config/botsort_tracker.json`, `build_tracker`); `RtspSessionScheduler` và các biến `PERSON_SEARCH_RTSP_*`; `PRODUCTION_PREFLIGHT_IDS`; preflight nạp mô hình thật ở chế độ production; kết quả đánh giá lần 2 |

**Tiêu chí hoàn thành.** Tìm "không có trạng thái", "botsort_candidate", "has_backpack" trong ba file
đều không còn kết quả; mỗi thay đổi ở trên có mục tương ứng.

### R5. Kiểm thử hồi quy giao diện

Đợt sửa cho điện thoại mới được kiểm tra ở 390 px; chưa chụp lại ở màn hình máy tính.

**Cách làm.**
1. Đưa kịch bản Playwright đang để trong scratchpad vào repo, ví dụ `frontend/ui-smoke/`
   (`run.mjs` chụp mọi trang theo vai trò và đo phần tử tràn khỏi màn hình; `case_status.mjs` kiểm
   tra bộ lọc trạng thái vụ việc). Dùng `playwright-core` với trình duyệt Edge có sẵn
   (`channel: 'msedge'`), không tải trình duyệt mới; thêm lệnh `npm run ui:smoke`.
2. Chạy ở ba cỡ: 390×844 (điện thoại), 768×1024 (máy tính bảng), 1440×900 (máy tính).
3. Xem từng ảnh chụp, không chỉ dựa vào số đo tự động.

**Tiêu chí hoàn thành.** Không trang nào có phần tử bị cắt ở cả ba cỡ; không có lỗi trong console
trình duyệt; bố cục máy tính giữ như trước đợt sửa.

### R6. Chuẩn bị dữ liệu demo

**Hiện trạng.** Mỗi camera mới có 60 giây đầu (736 track). Đủ để tìm kiếm, nhưng ít cảnh để minh họa
một người xuất hiện trên nhiều camera theo thời gian.

**Cách làm.**
1. Đưa script lập chỉ mục trong scratchpad vào `backend/tools/index_wildtrack.py`: tạo hoặc dùng lại
   camera `WT-CAM1..7` ở `GATE-A`, cắt đoạn theo `--start/--seconds`, upload qua API với cùng mốc thời
   gian gốc cho cả 7 camera, theo dõi tới khi job kết thúc.
2. Lập chỉ mục thêm đoạn 60–120 giây cho cả 7 camera (khoảng 50 phút trên máy hiện tại).
3. Sau khi chạy: `reconcile` sạch; nếu có job bị ngắt thì `retry-outbox`.
4. Chọn trước 3–4 truy vấn demo cho kết quả tốt (ưu tiên **tìm bằng ảnh**, vì văn bản/thuộc tính có
   Recall thấp trên WILDTRACK), ghi lại trong kịch bản demo (R7).
5. Sao lưu database, MinIO và Milvus sau khi dữ liệu demo đã chốt: `python tools/storage_backup.py
   backup`, rồi `verify <thư mục>`.
6. **Diễn tập khôi phục (bắt buộc trước demo):** ghi lại số track `READY`, một `track_id`, một
   `case_result_id`; dừng API/worker; chạy `python tools/storage_backup.py restore <thư mục> --yes`
   (với stack trống chỉ dựng lại khi bản sao lưu đã verify); kiểm tra lại: Giám sát viên tìm ra track
   đã ghi, mở được ảnh crop và full frame, Quản lý mở được vụ việc. Lần diễn tập trước trên dữ liệu
   nhỏ mất khoảng 5,5 giây (phần lớn là dựng lại Milvus); cần đo lại với dữ liệu demo thật.

**Tiêu chí hoàn thành.** Khoảng 1.400–1.500 track `READY` trên 7 camera; có bản sao lưu đã verify và
đã diễn tập khôi phục thành công; có danh sách truy vấn demo đã thử.

**Kết quả (2026-09-28).**
- `backend/tools/index_wildtrack.py` (đi qua API như Admin, chỉ dùng thư viện chuẩn; mật khẩu lấy từ
  `PERSON_SEARCH_ADMIN_PASSWORD` hoặc hỏi khi chạy; `--baseline` chuyển về YOLO11n + ByteTrack).
  Chạy `--start 60 --seconds 60`: 7 job `SUCCEEDED` trong 55 phút, +752 track, 0 lỗi. WILDTRACK nay
  1.488 track `READY` (C1 208, C2 254, C3 308, C4 188, C5 182, C6 159, C7 189), phủ 0–120 giây;
  toàn hệ thống 1.555. `reconcile` sạch.
- Truy vấn demo (tìm bằng ảnh, top 8, ảnh crop từ `files/wildtrack_evaluation_queries.json`, lưu ở
  `backend/var/demo-queries/`): **Q006** túi hoa, giày trắng — 8/8 đúng, 5 camera; **Q002** ba lô
  cam kéo vali — 8/8, 4 camera; **Q001** ba lô xanh caro — 8/8, 4 camera; **Q004** túi đeo trắng —
  7/8, 4 camera. Dự phòng Q003 (4/8). Không dùng Q005 (đám đông, kết quả lẫn người khác).
- Sao lưu `backups/20260928T172140Z` (521 MB, 1.557 file), `verify` đạt.
- Diễn tập khôi phục (API/worker dừng): PostgreSQL 1,5 s; MinIO 4,7 s (1.555 ảnh còn nguyên nên bỏ
  qua); **reindex Milvus 1.468 s (~24,5 phút)**, 1.554/1.555 vector, 1 vector lỗi
  `DEADLINE_EXCEEDED` nên lệnh trả exit 2; `reconcile` sau đó sạch (vector cũ còn trong collection).
  Sau khôi phục: tìm Q002 vẫn ra track mốc hạng 1, crop/full frame 200; Quản lý mở được vụ việc,
  ảnh của case result mốc 200; dashboard đúng.
- **Sửa và diễn tập lại (người thực hiện đồng ý):** nguyên nhân là mỗi vector cần một upsert và một
  truy vấn xác minh `Strong` (~0,94 s/vector). `StorageReindexer` nay ghi mỗi lô 200 vector bằng một
  `upsert_many` và xác minh bằng một truy vấn `existing_ids` (`track_id in [...]`); lô lỗi thì thử lại
  từng vector để lỗi tạm thời tự lành và vẫn chỉ đúng track hỏng. +3 unit test (711 pass). Diễn tập
  lại sau khi xóa 10 ảnh MinIO (gồm ảnh track mốc; `reconcile` báo `missing_objects: 10`):
  **khôi phục 28,8 s, exit 0** — PostgreSQL 1,8 s, MinIO 6,2 s (upload lại 10/10, bỏ qua 1.545),
  reindex **8,8 s** (1.555/1.555, 0 lỗi), reconcile 12 s sạch. Sau khôi phục: Q002 vẫn ra track mốc
  hạng 1, crop/full frame của track mốc có đúng kích thước byte như trước khi xóa; Quản lý mở được
  vụ việc và ảnh; dashboard đúng.

### R7. Kịch bản demo và bằng chứng RTSP

Đặc tả (architect §1, §10) yêu cầu trình diễn được việc nhận luồng RTSP do Quản trị viên thiết lập.

**Cách làm.**
1. Viết `files/demo-script.md`: thứ tự khởi động (storage → `scripts/rtsp.ps1 up` → API → worker →
   frontend), các bước trên giao diện theo từng vai trò, thời gian dự kiến, phương án dự phòng.
2. Luồng trình diễn đề xuất: Quản trị viên thêm camera RTSP và kiểm tra kết nối → bật AI → worker tự tạo
   phiên (khoảng 10 giây) → xem trạng thái hệ thống → Giám sát viên tìm bằng ảnh trên dữ liệu đã lập chỉ
   mục → lưu vụ việc, đánh dấu hoàn thành → Quản lý xem dashboard và hồ sơ.
3. Kiểm tra lại `PERSON_SEARCH_RTSP_NETWORKS` theo IP của mạng tại nơi bảo vệ (IP Wi-Fi thay đổi theo
   mạng; `rtsp.ps1 up` in sẵn giá trị cần đặt).
4. Quay video màn hình toàn bộ kịch bản làm phương án dự phòng khi máy hoặc mạng có sự cố.

**Tiêu chí hoàn thành.** Chạy trọn kịch bản hai lần liên tiếp không lỗi, trên chính máy demo; có video
dự phòng.

**Kết quả (2026-09-28).**
- `files/demo-script.md`: chuẩn bị, khởi động, làm nóng tìm kiếm, bốn phần A–D theo vai trò (thao
  tác, kết quả mong đợi, ý để nói), truy vấn thay thế, xử lý sự cố, trả dữ liệu về mốc.
- `frontend/ui-smoke/demo-run.mjs` (`npm run ui:demo`) chạy đúng kịch bản và quay video;
  `scripts/demo-reset.ps1` trả dữ liệu về bản sao lưu mốc (~70 giây).
- Trên máy demo, hai lần liên tiếp (mỗi lần từ mốc, API khởi động lại): 15/15 bước đạt, không lỗi
  HTTP/trang, 88 s và 85 s thao tác. RTSP `cam2` "Trực tuyến", worker tự tạo phiên sau 13–24 s.
  Video dự phòng không lời: `frontend/ui-smoke/output/demo/2026-09-28T18-28-24/demo.mp4` (83 s).
  Dữ liệu đã trả về mốc sau diễn tập.
- Dọn dữ liệu E2E theo yêu cầu của người thực hiện: camera `E2E-D9932C` (đã ngừng vận hành, 1 job,
  32 track) và vụ việc "E2E case" (2 kết quả, đều trỏ vào track E2E; không vụ việc nào khác tham
  chiếu). Xóa trong một transaction có kiểm tra số dòng, rồi `reconcile --delete-orphans` (32 ảnh,
  32 vector), `reconcile` sạch. Còn 8 camera, 1 vụ việc, 1.523 track. Mốc demo mới
  `backups/20260928T184653Z` (verify 1.525 file; `demo-reset.ps1` về mốc 68 s).
- Phát hiện khi diễn tập: lần tìm đầu sau khi khởi động API, cùng lúc worker xử lý RTSP, mất ~97 s
  (vượt timeout của script). Xử lý bằng bước làm nóng bắt buộc trước giờ demo (~31 s khi máy rảnh);
  sau đó tìm bằng ảnh ~8 s dù worker đang chạy.
- Còn lại cho người thực hiện: tự chạy kịch bản bằng tay trên máy demo và quay video có thuyết minh;
  kiểm tra IP mạng tại nơi bảo vệ (`PERSON_SEARCH_RTSP_NETWORKS`).

### R8. Đo RAM toàn stack

Architect §13 mục 4 mới đo gián tiếp (preflight báo còn khoảng 2 GB trống).

**Cách làm.** Ghi mức RAM của các container (`docker stats --no-stream`) và tiến trình Python (API,
worker và tiến trình con) ở ba trạng thái: rảnh; đang xử lý job; đang tìm kiếm. Đóng trình duyệt và
IDE khi đo. Ghi kết quả vào architect §13 và dùng cho báo cáo chương 8.

**Tiêu chí hoàn thành.** Có bảng số liệu ba trạng thái; kết luận có cần tách encoder truy vấn thành
tiến trình riêng hay không.

**Kết quả (2026-09-29).** Công cụ `backend/tools/measure_stack_memory.py`, kết quả
`backend/var/benchmark/stack-memory.json`; bảng chi tiết ở `files/report-data-guide.md` (C8.7).
Ứng dụng dùng ~3,7 GiB khi rảnh (API ~2 GiB sau khi nạp encoder truy vấn), ~8,0 GiB khi đang xử lý một
job (pipeline ≤ 4,7 GiB). Trạng thái "đang xử lý" đo bằng pipeline production chạy qua
`benchmark_sampling.py` thay cho worker, để không ghi vào dữ liệu demo. Kết luận: chưa cần tách encoder
truy vấn; khi demo phải đóng ứng dụng không cần thiết vì máy 16 GB gần hết RAM khi vừa xử lý vừa mở
IDE/trình duyệt.

### R9. *(Tùy chọn)* Xếp hạng lại image–text cho tìm bằng văn bản

Kết quả đánh giá hai lần: văn bản/thuộc tính → ảnh có Recall@4–16 = 0 trên WILDTRACK. Architect §6.2 cho
phép thử bước image–text matching của RaSa trên top ứng viên từ Milvus.

**Cách làm.** Thêm cờ cấu hình (mặc định tắt) để xếp hạng lại top 50–100 ứng viên bằng đầu ITM của
RaSa; chạy lại `tools/evaluate_wildtrack.py --modes text,attribute` để so sánh. Chỉ bật nếu Recall tăng
rõ và độ trễ tìm kiếm trên CPU chấp nhận được. Cập nhật đặc tả nếu bật.

### R10. *(Tùy chọn)* OpenVINO

Architect §9 ghi là phương án thử sau khi có baseline. Chỉ làm nếu R8 cho thấy thời gian xử lý là trở
ngại chính cho demo; đo trước/sau trên cùng đoạn video.

## 5. Kiểm tra trước buổi bảo vệ

- [ ] Storage, API, worker, frontend khởi động theo README trên máy demo, không lỗi.
- [ ] `ai_preflight.py` báo 4 mô hình PASS (YOLO11n, ByteTrack, BoT-SORT, RaSa).
- [ ] `reconcile` sạch; có bản sao lưu dữ liệu demo mới nhất.
- [ ] Không còn dữ liệu rác trên màn hình Quản trị viên.
- [ ] Đã chạy thử kịch bản demo trọn vẹn; có video dự phòng.
- [ ] `PERSON_SEARCH_RTSP_NETWORKS` khớp IP mạng tại nơi bảo vệ.
- [ ] Máy cắm sạc, tắt chế độ ngủ; đóng ứng dụng không cần thiết (RAM).

## 6. Nhật ký thực hiện

| Ngày | Mã | Kết quả |
| --- | --- | --- |
| 2026-09-28 | — | Lập kế hoạch |
| 2026-09-28 | R1 | Xóa 86 khu vực, 258 tài khoản, 82 camera, 62 job, 25 track rác; `reconcile` sạch (chi tiết ở mục R1) |
| 2026-09-28 | R2 | Chặn test ghi vào database không có hậu tố `_test`/`_citest`; thêm `scripts/test-db.ps1` |
| 2026-09-28 | R3 | Unit 708 pass (bật `REQUIRE_MODEL_TESTS`, không skip); kết nối storage 2 pass, 1 skip (failure injection, cần tắt một dịch vụ); dịch vụ dùng DSN riêng 21 pass; adapter 4 pass; migration và schema 7 pass; RTSP/MediaMTX 3 pass; E2E 2 pass (luồng AI thật với clip 10 giây mất 217 giây: nạp mô hình 44 giây, job 154 giây, tìm bằng văn bản 16 giây trong lần đầu) |
| 2026-09-28 | R3 | Lỗi 1 (test lỗi thời): `test_processing_schema.py` còn cấm `READY → FAILED`, trong khi migration `20260926_0011` đã cho phép để reconcile quarantine track hỏng. Sửa test: kiểm tra `READY → PENDING` bị chặn và `READY → FAILED` được phép |
| 2026-09-28 | R3 | Thiếu test: migration `20260927_0013` (trạng thái vụ việc) chưa có integration test. Thêm `test_case_status_migration_backfills_open_and_round_trips`: vụ việc cũ nhận `OPEN`; ràng buộc `status`/`closed_at`; downgrade về `0012` xóa cột và kiểu enum; upgrade lại khớp model |
| 2026-09-28 | R3 | Môi trường: IP máy đổi từ `192.168.110.145` sang `172.20.10.3`, nên MediaMTX bind vào IP không còn tồn tại (cổng không publish) và `PERSON_SEARCH_RTSP_NETWORKS` trong `backend/.env` đã cũ. Đã tạo lại MediaMTX trên IP mới; test RTSP chạy với allowlist ghi đè. Khi demo cần chạy lại `rtsp.ps1 up`, sửa `.env`, cập nhật URL camera `RTSP-CAM1` và khởi động lại API/worker (xem mục 5) |
| 2026-09-28 | R4 | Backend plan: §3, bảng endpoint (thêm `retire`/`reactivate`, sửa `DELETE` camera không tồn tại, `?status=`, crop `aspect`/`mark`), BE-06/08/14/16/17/18, §14 và nhật ký. Storage plan: nguyên tắc Case, STO-06, STO-15 (migration `0013` chi tiết), nhật ký; thay tham chiếu ADR-0001 đã gỡ cùng `docs/`. AI worker plan: BoT-SORT (§3, §3.5, AIW-11), `PRODUCTION_PREFLIGHT_IDS` (AIW-03), preflight nạp model thật (AIW-04), `RtspSessionScheduler` và biến `PERSON_SEARCH_RTSP_*` (AIW-17), bảng hai lần đánh giá (AIW-26), §12.1 và §12.2. Tìm "không có trạng thái", "botsort_candidate", "has_backpack" trong ba file: 0 kết quả |
| 2026-09-28 | R5 | Đưa kịch bản vào `frontend/ui-smoke/` (`npm run ui:smoke`, `npm run ui:case-status`, README); 3 cỡ × 20 màn hình không tràn, không lỗi console/HTTP; case-status 6/6 ok; đã xem ảnh desktop, máy tính bảng và các trang sửa ở điện thoại. Lỗi tìm ra và đã sửa: (1) trang Mô hình AI bấm thẻ Detector/Tracker không chọn được (prop `onPick` truyền xuống `<button>`, hồi quy từ `183c4d0`), (2) lần tìm kiếm đầu sau khi khởi động API báo "Không kết nối được tới máy chủ" do timeout 15 giây ngắn hơn thời gian nạp encoder, nay timeout tìm kiếm 120 giây, (3) trang Camera và Xử lý AI hiện "Không xác định" cho tiến trình AI và "Chưa xác minh" cho camera không RTSP; nay trang Xử lý AI lấy trạng thái worker từ API trạng thái hệ thống, trang Camera hiện Đã bật/Đã tắt và "Video tải lên" |
| 2026-09-28 | R6 | +752 track (60–120 s), WILDTRACK 1.488 track `READY`, `reconcile` sạch; 4 truy vấn demo bằng ảnh đã thử (3 cái 8/8); sao lưu verify; khôi phục lần 1 mất ~24,5 phút (reindex từng vector, 1 vector timeout); sửa reindex theo lô, diễn tập lại có xóa 10 ảnh: 28,8 s, exit 0, ảnh upload lại đủ. Chi tiết ở mục R6 |
| 2026-09-28 | R7 | `files/demo-script.md`, `npm run ui:demo` (quay video), `scripts/demo-reset.ps1`; diễn tập tự động hai lần liên tiếp đạt 15/15 bước; video dự phòng 83 s; phát hiện và xử lý tìm kiếm lần đầu chậm (~97 s) bằng bước làm nóng |
| 2026-09-28 | R7 | Dọn dữ liệu E2E (camera `E2E-D9932C`, vụ việc "E2E case", 32 track, 32 ảnh/vector); mốc demo mới `backups/20260928T184653Z` |
| 2026-09-29 | R8 | Đo RAM ba trạng thái, benchmark N=10/N=20 ở ngưỡng 0,1 (có RSS/CPU tiến trình con trên Windows), độ trễ tìm kiếm p50/p95; số liệu ở `report-data-guide.md` |
