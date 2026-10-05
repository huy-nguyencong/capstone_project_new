# Kế hoạch cải thiện Phần I (ứng dụng) trước bảo vệ

> Kế hoạch con cho Phần I của đồ án (chương 2 đến 8 của báo cáo và mã nguồn `backend/`, `frontend/`).
> Nó không mở rộng phạm vi hay thay đổi quyết định trong ba tài liệu nguồn (`architect.md`,
> `project_requirements.md`, `usecase_detail.md`). Mỗi task gồm ba phần bắt buộc: thay đổi mã,
> phép đo xác nhận, và chỗ cần sửa trong báo cáo `report/thesis-en/`. Không chạm vào chương 9 đến 11.

> **Quy ước theo dõi:** cập nhật trạng thái, file đã đổi, số đo và quyết định ngay trong file này.
> Số đo đưa vào báo cáo phải lấy từ artifact máy đọc được trong `backend/var/benchmark/` hoặc
> `backend/var/evaluation/`, không chép tay từ terminal.

## 0. Vì sao có kế hoạch này

Nhận xét phản biện (05/10/2026) nêu các điểm hội đồng sẽ hỏi, và thầy hướng dẫn đã hỏi trực tiếp
vì sao ứng dụng chiếm tới 8 GB RAM khi chạy. Bảng dưới nối mỗi câu hỏi với task trả lời nó.

| Câu hỏi dự kiến của hội đồng | Task trả lời |
| --- | --- |
| Vì sao ứng dụng chiếm 8 GB RAM? Có giảm được không? | A0, A1, A2, A4, A5 |
| Tìm bằng văn bản ra kết quả gần như ngẫu nhiên. Đó là lỗi cài đặt hay domain gap? | B1, B2 |
| Số liệu chính (bảng 8.2) đo ở ngưỡng 0.25, hệ thống chạy ở 0.1. Vì sao chưa đo lại? | B3 |
| Bộ đánh giá chỉ 6 truy vấn, kết luận gì được? | B3 |
| Vì sao không thử CLIP trong ứng dụng khi Phần II cho thấy CLIP hoạt động? | B4 |
| Timestamp RTSP lấy lúc nhận làm đứt track, sửa rẻ sao không sửa? | C1 |
| Precision phát hiện 0.43 nghĩa là gì, đo thế nào? | B6 |
| Trình diễn: tìm bằng văn bản trên demo có ra gì không? | B2, B5 |

## 1. Tổng quan và thứ tự thực hiện

| Mã | Task | Ưu tiên | Công sức | Phụ thuộc |
| --- | --- | --- | --- | --- |
| A0 | Phân tích và đo baseline bộ nhớ theo nguyên nhân | 1 | 0.5 ngày | - |
| A1 | Chỉ nạp các mô-đun RaSa cần cho suy luận | 1 | 1 ngày | A0 |
| A4 | Cắt bộ nhớ nền: Vite dev server, import torch, giới hạn Docker VM | 1 | 0.5 ngày | - |
| A5 | Đo lại toàn hệ thống và cập nhật báo cáo | 1 | 0.5 ngày | A1, A4 |
| C1 | Timestamp khung hình RTSP lấy từ PTS của luồng | 1 | 1 ngày | - |
| B3 | Đo lại ba hình thức ở ngưỡng 0.1, mở rộng bộ truy vấn lên ít nhất 20 | 1 | 1.5 ngày | - |
| B1 | Kiểm chứng đường xử lý văn bản trên miền huấn luyện của RaSa | 1 | 1 ngày | - |
| B2 | Phân tích nguyên nhân thất bại của tìm bằng văn bản trên WILDTRACK | 1 | 1 ngày | B1, B3 |
| B6 | Sửa cách trình bày kết quả và giao thức đo phát hiện trong báo cáo | 1 | 0.5 ngày | B2, B3 |
| B4 | So sánh CLIP với RaSa trên WILDTRACK (ngoại tuyến) | 2 | 1.5 ngày | B3 |
| A2 | Một bản mã hóa dùng chung cho server và worker | 2 | 1.5 ngày | A1 |
| A3 | Lượng tử hóa int8 động cho encoder (phiên bản encoder mới) | 3 | 1.5 ngày | A1, B3 |
| B5 | Bật re-rank ITM của RaSa cho truy vấn văn bản và đo | 1 (nâng từ 3 sau B1) | 1 ngày | B1 |
| C2 | Mã hóa và ghi appearance ngay khi track kết thúc | 3 | 2 ngày | C1 |
| E1 | Đồng bộ tóm tắt, chương 12 và slide với số liệu mới | 1 | 0.5 ngày | tất cả |

Thứ tự đề xuất: A0 → A1 → A4 → A5 → C1 → B3 → B1 → B2 → B6 → B4 → E1. Các task ưu tiên 2 và 3
chỉ làm nếu còn thời gian; mỗi task đều có thể dừng độc lập mà không để hệ thống ở trạng thái dở.

## 2. Nhóm A: bộ nhớ

### A0. Phân tích và đo baseline bộ nhớ theo nguyên nhân

**Vì sao 8 GB.** Số đo ngày 29/09 (`backend/var/benchmark/stack-memory.json`, bảng mục 8.3) cho
tổng khoảng 8.0 GiB khi đang xử lý. Phân tích mã nguồn và checkpoint cho thấy bốn nguyên nhân,
theo thứ tự lớn dần:

1. **Checkpoint RaSa chứa gấp đôi trọng số cần dùng.** `config/model_artifacts/rasa_cuhk_pedes_v1.pth`
   có 1,911 MiB trạng thái mô hình, đo bằng `torch.load(..., mmap=True)`:

   | Thành phần | MiB | Cần cho suy luận? |
   | --- | --- | --- |
   | `text_encoder` (BERT 12 lớp, gồm 6 lớp fusion và đầu MLM) | 561 | Một phần: chỉ các lớp chế độ `text` và `text_proj` |
   | `text_encoder_m` (bản momentum) | 561 | Không |
   | `visual_encoder` (ViT-B/16) | 328 | Có |
   | `visual_encoder_m` (bản momentum) | 328 | Không |
   | `image_queue`, `text_queue` (hàng đợi contrastive 256 x 65,536) | 128 | Không |
   | `vision_proj`, `text_proj` và các bản momentum, các đầu ITM/PRD/MRTD | 3 | Chỉ hai projection |

   Lớp `ALBEF` trong `backend/src/person_search/ai/encoders/rasa_vendor/model_person_search.py`
   là lớp huấn luyện: constructor tạo cả bản momentum và hàng đợi, nên mỗi lần nạp tốn ~1.9 GiB
   trong khi suy luận chỉ cần ~0.9 GiB, và chỉ ~0.6 GiB nếu bỏ 6 lớp fusion khi không re-rank.
2. **Đỉnh lúc nạp cao gấp đôi trạng thái ổn định.** `RasaRuntimeFactory.load` trong
   `backend/src/person_search/ai/encoders/rasa.py` khởi tạo `ALBEF()` với trọng số ngẫu nhiên
   (1.9 GiB cấp phát) rồi `load_state_dict` chép từ checkpoint mmap (thêm tới 1.8 GiB trang file
   được chạm). Đỉnh một tiến trình nạp có thể gần 3.7 GiB; bảng 8.3 ghi đỉnh nên con số
   4,267 MiB của "model processes" phản ánh đỉnh này chứ không phải mức ổn định.
3. **Mô hình được nạp hai lần.** Application server nạp một bản để mã hóa truy vấn
   (`services/query_encoder.py` qua `RasaImageProcessBackend`), worker nạp một bản nữa trong
   tiến trình con của `ai/encoders/image.py`. Hai bản độc lập, không chia sẻ trang.
4. **Mỗi tiến trình con import torch riêng.** Detector (`ai/detectors/ultralytics.py`) và encoder
   chạy ở hai tiến trình `spawn`; mỗi tiến trình trả ~300 đến 500 MiB cho runtime torch và
   ultralytics trước khi nạp trọng số nào. Vite dev server (318 MiB) và máy ảo Docker cũng tính
   vào tổng dù không thuộc ứng dụng.

**Code.** `backend/tools/measure_encoder_memory.py` (đã viết): nạp encoder theo từng bước trong
một tiến trình con (import torch, import mô-đun vendor, khởi tạo `ALBEF`, `torch.load` mmap,
`load_state_dict`, giải phóng checkpoint, một lần suy luận ảnh và văn bản) và ghi RSS cùng đỉnh
working set sau mỗi bước; chạy thêm một tiến trình con nữa đi đúng đường
`RasaRuntimeFactory.load` của production. Kết quả tại `var/benchmark/encoder-memory-<tag>.json`.

**Đo (đã chạy 05/10/2026, tag `before`).**

| Bước trong tiến trình encoder | RSS (MiB) | Đỉnh working set (MiB) |
| --- | --- | --- |
| Python trống | 22 | 22 |
| Sau `import torch` | 197 | 197 |
| Sau import mô-đun vendor (transformers, timm) | 410 | 410 |
| Sau khởi tạo `ALBEF()` với trọng số ngẫu nhiên | 2,226 | 2,226 |
| Sau `load_state_dict` từ checkpoint mmap | 3,961 | 3,961 |
| Sau giải phóng checkpoint (trạng thái ổn định) | 2,229 | 3,961 |
| Sau một lần suy luận ảnh và văn bản | 2,240 | 3,961 |
| Đường production `RasaRuntimeFactory.load` rồi 7 lần suy luận | 2,239 | 3,961 |

Đọc số: một bản encoder chiếm ổn định 2.2 GiB, trong đó 1.9 GiB là trạng thái mô hình và
0.4 GiB là runtime trước khi có trọng số nào; đỉnh lúc nạp 3.9 GiB vì trọng số ngẫu nhiên
(2.2 GiB) và các trang checkpoint được chép (1.7 GiB) cùng tồn tại. Chỉ 891 MiB của checkpoint
được suy luận dùng, và 583 MiB nếu bỏ 6 lớp fusion và đầu MLM (chế độ `text` chỉ chạy các lớp
trước `fusion_layer = 6`). Hai số đo khớp với bảng 8.3: application server 1,978 MiB sau
warm-up là một bản encoder; đỉnh "model processes" 4,267 MiB khi xử lý là đỉnh lúc nạp của bản
thứ hai cộng tiến trình detector.

Baseline toàn hệ thống: số đo ngày 29/09 (`stack-memory.json`, cùng mã nguồn hiện tại) được
giữ nguyên thành `var/benchmark/stack-memory-before.json`; không đo lại vì stack Docker không
chạy lúc làm A0 và mã chưa đổi. Tóm tắt (MiB): idle sau warm-up API 1,978, worker 338, Vite 318,
FFmpeg 286, container 515, Docker VM 828; khi xử lý thêm pipeline 3,313 (đo bằng công cụ chạy
pipeline thay worker), máy dùng tối đa 15,554 trên 16,122.

**Báo cáo.** Chưa sửa. Số liệu này là đầu vào cho A5; ba file JSON là nguồn cho bảng mới ở mục 8.3.

**Tiêu chí hoàn thành.** Đạt: có `encoder-memory-before.json`, `stack-memory-before.json`, và bảng
nguyên nhân ở trên được xác nhận bằng số đo.

**Trạng thái.** Xong 05/10/2026. File đổi: `backend/tools/measure_encoder_memory.py` (mới),
`backend/README.md` (một dòng hướng dẫn chạy). Kỳ vọng cho A1 được cụ thể hóa: ổn định dưới
1.0 GiB (0.4 runtime + 0.6 trọng số), đỉnh lúc nạp dưới 1.2 GiB nhờ khởi tạo `meta` và `assign=True`.

### A1. Chỉ nạp các mô-đun RaSa cần cho suy luận

**Code (đã làm 05/10/2026).**

- Mới: `backend/src/person_search/ai/encoders/rasa_vendor/inference_model.py` với lớp
  `RasaInferenceModel` chỉ gồm `visual_encoder`, `text_encoder.bert` (BertModel, không đầu MLM),
  `vision_proj`, `text_proj`; giữ nguyên tên tham số để checkpoint nạp không cần đổi khóa. Cờ
  `keep_fusion_layers` (mặc định `False`): chế độ `text` của BERT chỉ chạy các lớp trước
  `fusion_layer = 6`, nên 6 lớp fusion và đầu MLM bị bỏ; `select_state` lọc state dict theo
  đúng các mô-đun giữ lại, bỏ mọi khóa `*_m.*`, hàng đợi, `temp` và ba đầu phụ.
- `rasa.py`: `RasaRuntimeFactory(..., keep_fusion_layers=False)`;
  `load(full_training_module=False)` tạo mô-đun trên thiết bị `meta` rồi
  `load_state_dict(strict=True, assign=True)` từ checkpoint mmap, kiểm tra không còn tensor nào ở
  `meta`; nhánh `full_training_module=True` giữ lớp `ALBEF` gốc chỉ để đối chứng.
  `RasaRuntime.fusion_layers_loaded` ghi lại lựa chọn. `inspect_checkpoint` giữ nguyên (849 khóa).
- `rasa_vendor/vit.py`: một dòng đổi `torch.linspace(..., device="cpu")` kèm chú thích, vì `.item()`
  không chạy được trên tensor `meta`. Đây là thay đổi duy nhất trong mã vendor.
- Mới: `backend/tools/rasa_equivalence_check.py` (đối chứng vector hai đường nạp, mô tả trong
  README backend). `tools/measure_encoder_memory.py` đo đường production tự dùng đường mới.
- Không đổi `encoder_version`, không đổi collection Milvus.

**Đo (05/10/2026).**

| Số đo | Trước (ALBEF gốc) | Sau (RasaInferenceModel) |
| --- | --- | --- |
| Trọng số nạp | 1,911 MiB | 583 MiB |
| RSS ổn định sau suy luận | 2,239 MiB | 950 MiB |
| Đỉnh working set lúc nạp | 3,961 MiB | 983 MiB |
| Thời gian nạp (đã có trong page cache) | 19 đến 20 s | 4 đến 9 s |
| Mã hóa một crop ảnh, CPU 4 luồng | 1.22 đến 1.49 s | 1.17 đến 1.37 s |
| Mã hóa một câu | 0.08 đến 0.09 s | 0.09 đến 0.11 s |

Nguồn: `var/benchmark/encoder-memory-before.json`, `encoder-memory-after-a1.json`,
`rasa-equivalence.json`. Thời gian suy luận của hai đường nằm trong nhiễu đo (hai lần chạy cùng
đường mới cho 1.37 và 1.22 s); giữ tham số tham chiếu thẳng vào mmap, không sao chép ra bộ nhớ
ẩn danh, vì bản sao chỉ nâng đỉnh lên 1,583 MiB mà không nhanh hơn.

Tương đương vector: 50 crop WILDTRACK và 10 câu, sai khác lớn nhất 0.0, cosine nhỏ nhất
1.00000000 giữa đường cũ và mới, nên NFR-09 được giữ mà không cần index lại.

Kiểm thử: thêm `tests/unit/test_rasa_inference_model.py` (lọc state dict với và không có lớp
fusion, giữ thứ tự khóa, cờ của factory, và một test `model_real` nạp checkpoint thật bằng đường
mới); `scripts/check.ps1` (pytest `-m unit`, ruff, compileall) qua toàn bộ.

**Báo cáo (đã sửa).** Mục 3.5.3 thêm câu về checkpoint huấn luyện và phần được nạp; mục 6.2.1
thêm đoạn "The RaSa checkpoint is loaded selectively" với số trước và sau; PDF build lại không
lỗi. Bảng bộ nhớ toàn hệ thống ở 8.3 và chương 12 đợi A5.

**Lưu ý cho A2.** Tham số giờ là trang file ánh xạ từ cùng một file checkpoint, nên hai tiến trình
(application server và worker) nạp cùng file chia sẻ trang vật lý qua page cache của Windows.
A5 cần đo mức dùng của cả máy, không chỉ cộng RSS từng tiến trình, trước khi quyết định có làm A2.

**Tiêu chí hoàn thành.** Đạt toàn bộ: vector trùng, test qua, số đo `after-a1` có trong JSON.

**Trạng thái.** Xong 05/10/2026.

### A2. Một bản mã hóa dùng chung cho server và worker

**Vì sao xếp ưu tiên 2.** Sau A1, mỗi bản chỉ còn dưới 1 GiB, nên gộp hai bản tiết kiệm thêm
khoảng 0.7 đến 0.9 GiB, đổi lại một thành phần triển khai mới. Làm nếu A5 chưa đạt mục tiêu.

**Code.**

- `services/searches.py` đã có `HttpEncoderGateway` (POST `/encode/image`, `/encode/text`). Thêm
  tiến trình `person_search.encoder_service`: một server HTTP nhỏ chỉ nghe trên loopback, nạp
  RaSa một lần qua `RasaRuntimeFactory`, có khóa suy luận và hàng đợi ưu tiên để truy vấn người
  dùng không phải đợi sau các crop đang index.
- Worker: `RasaImageProcessBackend` nhận thêm chế độ `remote` dùng cùng gateway HTTP; giữ chế độ
  tiến trình con làm mặc định khi không cấu hình biến môi trường `ENCODER_SERVICE_URL`.
- Application server: khi có `ENCODER_SERVICE_URL`, `InProcessQueryEncoder` nhường cho
  `HttpEncoderGateway`.
- Health check `/health/ready` của server báo encoder service có sẵn hay không.

**Đo.** Độ trễ tìm kiếm (`tools/benchmark_search_latency.py`) khi worker rảnh và khi worker đang
xử lý; bộ nhớ toàn hệ thống. Độ trễ tìm ảnh không được tăng quá 20% so với bảng 8.4 khi worker rảnh.

**Báo cáo.** Mục 5.1.1 và hình 5.1 thêm thành phần encoder service; 5.1.2 "Design Principles"
sửa câu "queries are encoded with the same RaSa weights"; 7.1 thủ tục khởi động; 8.3 số đo.

**Trạng thái.** Chưa làm. Chỉ làm nếu cần sau A5.

### A3. Lượng tử hóa int8 động cho encoder

**Vì sao ưu tiên 3.** `torch.ao.quantization.quantize_dynamic` trên các lớp `nn.Linear` giảm
trọng số Linear còn một phần tư và thường tăng tốc suy luận CPU 1.5 đến 2 lần, nhưng vector đầu ra
thay đổi, nên theo thiết kế phải là phiên bản encoder mới với collection Milvus riêng và phải
index lại dữ liệu demo. Chỉ làm khi B3 đã có bộ đánh giá đủ lớn để chứng minh không mất chất lượng.

**Code.** Mục registry mới `rasa_cuhk_pedes_int8_v1` trong `config/models.*.json` với cùng
artifact; cờ lượng tử hóa trong `RasaRuntimeSettings`; migration tạo collection mới theo cơ chế
đã có (mục 5.3.2).

**Đo.** R@k và MRR của cả ba hình thức trên bộ truy vấn B3 so với fp32; thời gian mã hóa mỗi
track trong `tools/benchmark_sampling.py`; bộ nhớ encoder.

**Báo cáo.** 6.1.4 "Encoder" thêm đoạn so sánh; 8.3 bảng 8.3 thêm cột; 12.3 cập nhật hướng tăng tốc.

**Trạng thái.** Chưa làm.

### A4. Cắt bộ nhớ nền không thuộc mô hình

**Khảo sát trước khi sửa (05/10/2026).**

- Application server và tiến trình chính của worker không import torch, ultralytics hay
  transformers ở mức module: sau `create_app` và sau import `workers.production_main`, RSS đều
  138 MiB và chỉ có PIL, av, numpy, flask, sqlalchemy, pymilvus, minio được nạp. Không cần sửa.
- Tiến trình con detector đã import `ultralytics` trễ trong hàm con và nhận `OMP_NUM_THREADS = 2`
  từ `apply_resource_environment`, nên torch chạy đúng 2 luồng. Đo từng bước: import torch
  196 MiB, import ultralytics 214, nạp YOLO11n 234, sau lần dự đoán đầu 376, ổn định 403 MiB,
  đỉnh 415 MiB. Đây là phần nền của torch, không cắt thêm được nếu không bỏ torch.
- Vite dev server: 325 MiB với 4 tiến trình node (khớp 318 MiB ở bảng 8.3); `vite preview`
  145 MiB; phục vụ `frontend/dist` từ chính API: 0 MiB thêm.
- Máy ảo WSL 2 của Docker Desktop: không có `.wslconfig`, nên mặc định được phép tới 50% RAM;
  đo 828 đến 1,156 MiB khi container chỉ dùng 515 MiB.

**Code (đã làm).**

- Mới `backend/src/person_search/api/frontend.py`: khi `PERSON_SEARCH_STATIC_DIR` (hoặc
  `STATIC_FRONTEND_DIR`) trỏ tới thư mục build, API phục vụ `index.html` cho mọi đường dẫn
  không phải `/api/` hay `/health/`, phục vụ tệp tĩnh có thật, `assets/` băm tên được
  `Cache-Control: public, max-age=31536000, immutable`, và trang nhận
  Content-Security-Policy riêng (`default-src 'self'`, cho phép blob và data cho ảnh) thay cho
  chính sách `default-src 'none'` của API. Đăng ký sau `register_api` nên các rule API và health
  luôn thắng; đường dẫn ngoài thư mục bị chặn bởi `safe_join`. `app.py` đọc biến môi trường và
  gọi `register_static_frontend`. `.env.example` có dòng mới kèm chú thích.
- Kiểm chứng với bản build thật: `index.html` không có script hay style nội tuyến, hai tệp
  `assets/*.js` và `*.css` trả 200 với cache dài hạn, đường dẫn SPA như `/cases` trả trang,
  `/api/v1/<không tồn tại>` vẫn trả 404 JSON.
- Mới `infra/wslconfig.example` (`memory=3GB`, `processors=2`, `swap=0`) kèm hướng dẫn; không
  tự chép vào `%UserProfile%` vì file này áp dụng cho mọi distro WSL 2 trên máy, người dùng
  chép bằng một lệnh trong README.
- Không đổi gì ở detector và worker (xem khảo sát).

**Kiểm thử.** Mới `tests/unit/test_static_frontend.py` (6 test: không cấu hình thì không phục
vụ, trang và route SPA kèm CSP, cache của assets, API/health không rơi về trang, đường dẫn
ngoài thư mục, thiếu index là lỗi cấu hình). `scripts/check.ps1` qua: 727 unit test, ruff,
compileall.

**Đo.** Với cách chạy demo mới, nhóm `frontend_vite` biến mất khỏi bảng bộ nhớ (trừ 318 MiB);
Docker VM đợi người dùng áp `.wslconfig` rồi A5 đo lại. Số đo toàn hệ thống ở A5.

**Báo cáo (đã sửa).** Mục 7.1 "Environment" nêu web application được build một lần và do
application server phục vụ cùng origin, và máy ảo WSL 2 được giới hạn 3 GB; "Start-up
procedure" bỏ bước khởi động web application riêng. README gốc có mục Terminal 4 mới và mục
giới hạn RAM Docker. PDF build lại không lỗi.

**Trạng thái.** Xong 05/10/2026, trừ việc chép `.wslconfig` vào máy (thủ công, một lệnh) trước A5.

### A5. Đo lại toàn hệ thống và cập nhật báo cáo

**Đo (05/10/2026, cùng giao thức mục 8.3; stack như khi demo: storage, MediaMTX + 7 FFmpeg, API
phục vụ `frontend/dist`, worker rảnh, không Vite).** Đơn vị MiB, giá trị lớn nhất mỗi trạng thái.

| Thành phần | Rảnh sau warm-up (trước / sau) | Đang tìm kiếm (trước / sau) | Đang xử lý (trước / sau) |
| --- | --- | --- | --- |
| Container Docker (5) | 515 / 363 | 517 / 373 | 524 / 378 |
| Application server (đã nạp encoder) | 1,978 / 1,134 | 2,037 / 1,173 | 1,990 / 1,149 |
| Worker (rảnh) | 338 / 300 | 338 / 339 | 272 / 346 |
| Web application (Vite / do API phục vụ) | 318 / 0 | 253 / 0 | 120 / 0 |
| FFmpeg 7 luồng | 286 / 286 | 285 / 365 | 243 / 361 |
| Pipeline AI, đỉnh (chính + con) | - | - | 4,772 / 2,098 |
| **Tổng tiến trình ứng dụng** | **3,435 / 2,083** | **3,430 / 2,250** | **7,921 / 4,332** |
| Máy ảo Docker (Vmmem), tính riêng | 828 / 3,184 | 839 / 1,686 | 817 / 1,676 |

Mục tiêu "tổng khi xử lý không quá 4.5 GiB" đạt với tiến trình ứng dụng (4.2 GiB), chưa đạt nếu
cộng máy ảo Docker. Pipeline: đỉnh tiến trình chính 728, tiến trình con 1,370 (detector ~0.4 GiB
và encoder ~1.0 GiB). Độ trễ tìm kiếm (10 lượt mỗi hình thức, máy đang thiếu RAM vì ứng dụng
khác): ảnh p50 1,169 ms, văn bản 109 ms, thuộc tính 100 ms, cùng mức bảng 8.4.

**Phát hiện về máy ảo Docker.** Số Vmmem chủ yếu là page cache Linux bên trong VM và phụ thuộc
thời gian VM đã chạy: 828 MiB ngày 29/09 (VM chạy lâu), 3,184 ngay sau khởi động lại ngày 05/10,
1,686 sau khoảng 40 phút. Thử cả ba cấu hình trong phiên đo: có `memory=3GB`, có thêm
`autoMemoryReclaim=gradual`, và không có `.wslconfig`: Vmmem đều ở 3.0 đến 3.2 GiB trong 5 đến 6
phút đầu, xả cache bên trong VM (`drop_caches`) chỉ hạ xuống 2.5 GiB. Kết luận: giới hạn 3 GB
chặn trần (mặc định WSL cho phép tới 8 GB) chứ không làm nhỏ lại; giữ cấu hình và ghi đúng như
vậy trong báo cáo. `infra/wslconfig.example` có thêm `autoMemoryReclaim=gradual` (WSL 2.6.1 hỗ trợ).

**Sự cố khi đo, cần biết khi demo.** Sau `wsl --shutdown` và khởi động lại Docker Desktop, cổng
chuyển tiếp 127.0.0.1 của một số container (PostgreSQL, MinIO, có lần cả Milvus) nhận kết nối rồi
đóng ngay ("server closed the connection unexpectedly"), dù container đã healthy và trả lời được
từ bên trong. Khắc phục: `docker restart <container>` từng container bị lỗi rồi thử lại từ host.
Nên đưa bước kiểm tra này vào thủ tục khởi động demo. Ngoài ra máy tính đã ngủ hơn 6 giờ giữa
phiên đo, làm các tiến trình nền bị dừng; các trạng thái bị ảnh hưởng đã được đo lại.

**Báo cáo (đã sửa).** Mục 8.3 "Storage and memory" thay bằng bảng 8.5 (trước và sau theo ba
trạng thái, máy ảo Docker tách riêng) cùng đoạn giải thích ba nguyên nhân giảm và đoạn điều kiện
đo cập nhật; mục 12.2 Part I sửa câu về bộ nhớ; mục 12.3 thêm hướng dùng chung một tiến trình
encoder. `files/report-data-guide.md` ba dòng C8.7 về RAM cập nhật theo. PDF build lại không lỗi.

**Nguồn số liệu.** `backend/var/benchmark/stack-memory-before.json`, `stack-memory-after.json`,
`stack-memory-processing-proxy-run-a5.json`, `search-latency-a5.json`.

**Trạng thái.** Xong 05/10/2026. Phần còn lại lớn nhất là hai bản encoder truy vấn (API và
worker), mỗi bản ~1 GiB kể cả runtime torch: đó là A2 nếu cần giảm thêm.

## 3. Nhóm B: chất lượng tìm kiếm bằng văn bản và thuộc tính

### B1. Kiểm chứng đường xử lý văn bản trên miền huấn luyện của RaSa

**Dữ liệu.** Không có CUHK-PEDES hay Market-1501 trong máy. Dùng bản Hugging Face
`MaulikMadhavi/CUHK-PEDES-processed` (tập train, 34.052 ảnh 128x384, mỗi ảnh mang đủ caption
của identity đó), tải 2 shard (~100 MB) vào `backend/var/datasets/cuhk_pedes_processed/`;
identity suy từ tên file theo quy ước 5 bộ nguồn. Checkpoint đang dùng được tải lại từ link
Google Drive chính thức của RaSa và so SHA-256: trùng khớp từng byte (bc85da09...).

**Code (đã làm 05/10/2026).**

- Mới `backend/tools/rasa_domain_sanity.py`: đi đúng `build_rasa_query_gateway` (ảnh PNG qua
  `gateway.image`, câu qua `gateway.text`), xếp hạng tích vô hướng; đo text→image và
  image→image theo identity, lưu vector; tùy chọn `--itm-queries` chạy xếp hạng lại bằng đầu
  ITM đúng như `evaluation()` trong `Retrieval.py` gốc (nạp `full_training_module=True`).
- Đối chiếu mã vendor với upstream ở commit đã ghim: `xbert.py`, `vit.py`,
  `model_person_search.py`, `config_bert.json` chỉ khác các shim tương thích (và một dòng
  của A1). Tiền xử lý ảnh (Resize 384x384 bicubic, chuẩn hóa CLIP) và cách lấy CLS,
  `mode="text"`, `max_words=50` trùng upstream. BERT vendor cho cùng đầu ra với BertModel
  chuẩn của Transformers khi nạp cùng trọng số (sai khác 1e-6).
- **Lỗi tìm được:** ứng dụng tokenise bằng `transformers.BertTokenizer` (thêm [SEP] cuối câu),
  trong khi RaSa huấn luyện và đánh giá bằng tokenizer riêng `models/tokenization_bert.py`
  viết "[CLS] X" không có [SEP]. Sửa `RasaPreprocessor.text` dùng tokenizer vendor;
  test `test_tokenizer_is_offline_uncased_padded_and_truncated` cập nhật. Vector ảnh không
  đổi nên không cần index lại.
- `pyarrow` cài thêm vào venv cho công cụ (không đưa vào requirements khóa hash).

**Đo (05/10/2026, 600 ảnh ngẫu nhiên, 541 identity, caption đầu của mỗi ảnh).**

| Phép đo | R@1 | R@5 | R@10 | Hạng đúng đầu tiên median |
| --- | --- | --- | --- | --- |
| image→image cùng identity (109 truy vấn) | 1,000 | 1,000 | 1,000 | 1 |
| text→image, vector tương phản, tokenizer chuẩn có [SEP] (cũ) | 0,020 | 0,070 | 0,137 | 88 |
| text→image, vector tương phản, tokenizer RaSa (mới) | 0,035 | 0,113 | 0,177 | 70 |
| ngẫu nhiên (kỳ vọng) | 0,002 | 0,008 | 0,017 | 300 |
| Tập con 150 ảnh, 40 caption: vector tương phản | 0,050 | 0,175 | 0,375 | 23 |
| Tập con 150 ảnh, 40 caption: xếp hạng lại ITM top-32 | 0,650 | 0,675 | 0,675 | 1 |

**Kết luận.** (1) Không có lỗi cài đặt ở đường ảnh: image→image hoàn hảo. (2) Vector tương
phản của RaSa chỉ là bộ sinh ứng viên; con số công bố 76,5% R@1 đến từ bộ xếp hạng lại ITM
trên top-128 trong mã đánh giá gốc, điều mà ứng dụng tắt (mục 3.5.3 cũ viết "chưa cho thấy
có ích"). ITM trên top-32 đưa R@1 từ 0,05 lên 0,65 ngay trên miền huấn luyện, chi phí ~50 ms
mỗi ứng viên trên CPU. Đây là nguyên nhân thứ nhất của tìm văn bản yếu, trước cả domain gap.
(3) Lỗi [SEP] là thật nhưng nhỏ: R@10 0,137 → 0,177 trên CUHK-PEDES; trên WILDTRACK (chạy
lại từ cache gallery) kết quả trong nhiễu: văn bản R@12/16 0,038, MRR 0,021; thuộc tính R@16
0,038, MRR 0,015. Bảng 8.2 cập nhật theo lần chạy cuối (`wildtrack-v2-conf010-rasatok.json`).

**Hệ quả cho các task sau.** B5 (bật re-rank ITM trên top-k) lên ưu tiên 1 và là hướng cải
thiện chính; B2 vẫn cần để định lượng phần domain gap còn lại; A1 giữ mặc định bỏ lớp fusion
nhưng B5 sẽ cần `keep_fusion_layers=True` cho đường tìm văn bản (+0,25 GiB).

**Báo cáo (đã sửa).** Mục 8.2 thêm đoạn "Pipeline check on the training domain" và sửa
Discussion (hai nguyên nhân), bảng 8.2 và Method theo lần chạy với tokenizer RaSa; mục 3.5.3
sửa câu về re-ranking và nêu tokenizer; 12.2 và 12.3 nêu hai nguyên nhân và bước đầu tiên là
bật re-rank; tóm tắt và 1.4 sửa câu nguyên nhân. README backend mô tả công cụ.

**Nguồn.** `backend/var/evaluation/rasa-domain-sanity.json` (kèm vector),
`wildtrack-v2-conf010-rasatok.json`, `var/tmp/rasa_cuhk_checkpoint_drive.pth` (bản tải
đối chiếu, có thể xóa).

**Trạng thái.** Xong 05/10/2026.

### B2. Phân tích nguyên nhân thất bại trên WILDTRACK

**Code (đã làm 05/10/2026).** Mới `backend/tools/wildtrack_text_diagnostics.py` (mô tả trong README
backend), chạy từ cache gallery của B3, embedding hai gallery nhãn cache ở
`var/evaluation/wildtrack-diag-embeddings.json`, ảnh ghép ở `var/evaluation/color-queries/`.
Kết quả `var/evaluation/wildtrack-text-diagnostics.json`.

**Đo (05/10/2026, chỉ vector, 26 truy vấn).**

1. Kích thước crop pipeline (1.526 track): chiều cao median 243 px (p10 134, p90 580); 1.100
   thấp hơn 384 px của crop huấn luyện, 122 thấp hơn 128 px; tỉ lệ rộng/cao median 0,38 so với
   0,33 của CUHK-PEDES. Crop nhỏ nhưng không nhỏ tới mức giải thích thất bại.
2. Cùng khung đại diện, cắt theo box nhãn tay thay cho box detector (947 track thay được):
   văn bản R@16 0,038 → 0,192, hạng đúng đầu tiên median 73 → 67; thuộc tính R@16 0,038 → 0,115.
3. Gallery nhãn: crop cao nhất mỗi người mỗi camera, 1.439 crop của 266 người: văn bản R@8 0,115,
   R@16 0,192, median 107; thuộc tính R@8 0,077.
4. Cosine truy vấn văn bản với gallery: trung bình 0,19, độ lệch chuẩn 0,04, track đúng trung
   bình 0,21, top-1 0,30: người đúng chỉ cao hơn đám đông chưa tới nửa độ lệch chuẩn (trên
   CUHK-PEDES: cặp đúng cao hơn một độ lệch chuẩn, B1). Sáu truy vấn màu đơn cho top-16 gần như
   cùng một tập (Jaccard trung bình giữa các cặp 0,30; 47 track riêng biệt trên 96 chỗ;
   "a person wearing a red top" không có áo đỏ nào trong top 16), bị chi phối bởi các crop cận
   cảnh tóc và áo tối.

**Kết luận.** Box sát hơn và khung tốt hơn chỉ giúp ít (R@16 lên 0,19); với crop tay chọn kỹ
vector vẫn yếu, nên phần còn lại nằm ở encoder (domain gap thật) chứ không ở detector hay chọn
khung. Vector xếp hạng theo mức độ crop "giống crop huấn luyện" hơn là theo nội dung câu; đầu ITM
(B5) sửa được phần lớn điều đó. Hai nguyên nhân nêu ở 8.2 Discussion được giữ nguyên, nay có
số liệu cho nguyên nhân thứ hai.

**Báo cáo (đã sửa).** Mục 8.2 thêm đoạn "Where the vector search fails" trước đoạn re-ranking,
với bốn số liệu trên; `report-data-guide.md` thêm dòng C8.4.

**Trạng thái.** Xong 05/10/2026.

### B3. Đo lại ở cấu hình hiện hành và mở rộng bộ truy vấn

**Code (đã làm 05/10/2026).**

- Mới `files/wildtrack_evaluation_queries_v2.json`: 6 truy vấn cũ giữ nguyên + 20 identity mới
  (WT-Q007 đến WT-Q026), chọn trong số người xuất hiện trên cả 7 camera với ít nhất 30 box cao hơn
  120 px; mô tả tiếng Anh và bộ thuộc tính viết từ bảng ghép 3 crop trên 3 camera khác nhau, chỉ
  dùng từ vựng thuộc tính của ứng dụng; bỏ identity 63 và 161 vì đi cạnh người mặc giống hệt
  (64 và 134 giữ lại, gắn thẻ `walks_with_similar_person`). Ảnh truy vấn là box cao nhất nằm trọn
  trong khung hình. `selection_policy` ghi trong file.
- `evaluation/metrics.py`: `wilson_interval` và trường `recall@k_ci95` trong `recall_summary`.
- `tools/evaluate_wildtrack.py`: `--gallery-cache` ghi kết quả pipeline (metric, timing, gallery
  kèm embedding) sau mỗi camera, dùng lại khi khóa (model, cấu hình, N, IoU) trùng, tiếp tục từ
  camera chưa xong nếu bị ngắt. Lý do: pipeline trên 7 x 400 frame mất ~65 phút; lần chạy đầu
  bị harness dừng ở phút 50 và mất trắng vì cache chỉ ghi ở cuối.
- Test: `test_evaluation.py` thêm test Wilson; 9 test qua.

**Đo (05/10/2026, cấu hình hiện hành: YOLO11n ngưỡng 0,1, ByteTrack, RaSa, mọi frame; gallery
1.526 track; 26 truy vấn; mỗi truy vấn có 5 đến 33 track đúng).**

| Hình thức | R@4 | R@8 | R@12 | R@16 | MRR | R@8 khoảng tin cậy 95% | Hạng đúng đầu tiên (median) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ảnh | 0,846 | 0,885 | 0,885 | 0,885 | 0,671 | 0,71 đến 0,96 | 1 (thất bại ở hạng 99, 109, 553) |
| Văn bản | 0 | 0,038 | 0,038 | 0,038 | 0,021 | 0,01 đến 0,19 | 73 |
| Thuộc tính | 0 | 0 | 0 | 0 | 0,013 | 0 đến 0,13 | 80 |

Tách theo nhóm: 6 truy vấn cũ ảnh R@8 1,0 / văn bản 0 / thuộc tính 0; 20 truy vấn mới ảnh R@8
0,85 / văn bản 0,05 / thuộc tính 0. Phát hiện người ở ngưỡng 0,1: precision 0,433, recall 0,637
(TP 27.194, FP 35.602, FN 15.527, IoU 0,5); 491 trong 1.526 track không khớp người có nhãn;
825 trong 1.639 người có nhãn được ít nhất một track phủ. Kết luận cho B1/B2: với 5 đến 33 track
đúng trong 1.526, thứ tự ngẫu nhiên cho hạng đúng đầu tiên median khoảng 150; văn bản và thuộc
tính đạt 73 và 80, tức là có tách nhưng rất yếu, chưa phải hoàn toàn ngẫu nhiên.

Nguồn: `backend/var/evaluation/wildtrack-v2-conf010.json`, cache
`wildtrack-gallery-conf010.json` (dùng lại cho B1, B2, B4 không cần chạy lại pipeline).

**Báo cáo (đã sửa).** Mục 8.2: "Method" viết lại (26 truy vấn, cách chọn, khoảng tin cậy), bảng
8.2 thay bằng kết quả hiện hành, đoạn "Person detection and tracking" với số mới, "Discussion"
cập nhật số; mục 12.2 bỏ câu "the evaluation is incomplete" và sửa câu "no query has a correct
result" thành 1/26 văn bản; mục 12.3 chỉ còn so sánh ByteTrack với BoT-SORT.
`files/report-data-guide.md` các dòng C8.4 cập nhật; README backend mô tả `--gallery-cache`.

**Trạng thái.** Xong 05/10/2026. B6 còn phải viết giao thức đo phát hiện và sửa câu "works but
with low quality" ở 12.1; B2 dùng cache gallery để chẩn đoán.

### B4. So sánh CLIP với RaSa trên WILDTRACK (ngoại tuyến)

**Mục đích.** Trả lời câu hỏi "vì sao không thử CLIP" bằng số đo trên chính dữ liệu của đề tài,
và nối với Phần II bằng cùng encoder cơ sở.

**Code.**

- `backend/src/person_search/evaluation/clip_gateway.py`: lớp đánh giá cài `EncoderGateway`
  (`image`, `text`) bằng `open_clip`, mặc định ViT-B/16 (vừa RAM máy demo), tùy chọn ViT-H/14
  laion2B như Phần II nếu đủ RAM. Chỉ dùng trong công cụ đánh giá, không đăng ký vào registry.
- `tools/evaluate_wildtrack.py` thêm `--encoder rasa|clip-vit-b16|clip-vit-h14`: gallery được
  mã hóa lại bằng encoder chọn, phần phát hiện và theo dõi dùng chung.
- Chạy trên bộ truy vấn B3, ghi `var/evaluation/wildtrack-v2-clip-*.json`.

**Quyết định sau khi đo.** Nếu CLIP hơn RaSa rõ ở văn bản và không kém đáng kể ở ảnh, ghi nhận
là hướng thay encoder (phiên bản encoder mới, collection mới) cho mục 12.3 và nối thẳng với
mục 12.4.2 "Bringing the Two Parts Together". Không đổi encoder trong ứng dụng trước bảo vệ
trừ khi còn dư thời gian sau E1.

**Báo cáo.** Mục 8.2 thêm bảng so sánh hai encoder; mục 6.1.4 "Encoder" sửa câu khẳng định
CLIP "separate small clothing differences less well" thành câu có số liệu.

**Trạng thái.** Chưa làm.

### B5. Bật re-rank ITM của RaSa cho truy vấn văn bản

**Code (đã làm 05/10/2026).**

- `rasa_vendor/inference_model.py`: với `keep_fusion_layers=True` giữ thêm `itm_head`
  (`select_state` giữ `itm_head.*`); `rasa.py`: `RasaRuntime.image_tokens(image)` (577x768) và
  `RasaRuntime.itm_scores(text, tokens)` chạy đúng như `evaluation()` của RaSa (text mode →
  fusion mode → logit "match"), theo lô 8 ứng viên.
- `ai/encoders/image.py`: tiến trình con nhận thêm lệnh `encode_tokens` và `itm`; backend và
  `build_rasa_query_gateway(..., keep_fusion_layers=True)`; `query.py` thêm `image_tokens`,
  `itm_scores`; `services/query_encoder.py` chuyển tiếp hai hàm này.
- Mới `services/text_rerank.py`: `TextRerankService.rerank(text, candidates, keep, ...)` lấy
  khung đại diện từ MinIO, crop đúng như lúc index, lấy token ảnh qua tiến trình encoder, cache
  `<track_id>.npy` float16 trên đĩa (`PERSON_SEARCH_ITM_TOKEN_CACHE`), chấm ITM, trả lại theo
  thứ tự ITM với `matching_score = sigmoid(logit)`; ứng viên thiếu khung được giữ sau các ứng viên
  đã chấm. `services/track_search.py`: `search(..., pool=N)` với `MAX_POOL = 128`, kết quả mang
  `frame_object_key`; `storage/milvus/vectors.py`: `ef = max(64, limit)`.
- `services/searches.py`: `SearchResponse.reranked`; TEXT/ATTRIBUTES qua re-rank khi bật;
  API trả trường `reranked`. `app.py` đọc `PERSON_SEARCH_TEXT_RERANK_TOP_N` (0 = tắt, 16..128)
  và nạp encoder truy vấn với lớp fusion khi bật. `.env.example` có hai biến mới.
- Mới `tools/evaluate_wildtrack_rerank.py` (đánh giá ngoại tuyến từ cache gallery, token cache
  float16) và `tools/warm_itm_cache.py` (tính trước token cho mọi track READY). Test mới
  `tests/unit/test_text_rerank.py` (6 test); `test_rasa_inference_model.py` cập nhật;
  check script qua: 740 unit test.

**Đo ngoại tuyến (05/10/2026, gallery 1.526 track, 26 truy vấn, cùng cache của B3).**

| Hình thức, tầng | R@4 | R@8 | R@12 | R@16 | MRR | Hạng đúng đầu tiên median |
| --- | --- | --- | --- | --- | --- | --- |
| Văn bản, chỉ vector | 0 | 0 | 0,038 | 0,038 | 0,021 | 73 |
| Văn bản, ITM N=32 | 0,115 | 0,115 | 0,115 | 0,154 | 0,104 | 73 |
| Văn bản, ITM N=64 | 0,269 | 0,308 | 0,423 | 0,423 | 0,248 | 73 |
| Văn bản, ITM N=128 | 0,346 | 0,423 | 0,462 | 0,500 | 0,329 | 18 |
| Thuộc tính, chỉ vector | 0 | 0 | 0 | 0,038 | 0,015 | 111 |
| Thuộc tính, ITM N=64 | 0,115 | 0,115 | 0,154 | 0,231 | 0,105 | 111 |
| Thuộc tính, ITM N=128 | 0,115 | 0,154 | 0,269 | 0,269 | 0,116 | 88 |

Người đúng nằm trong top-16/64/128 của vector: văn bản 1/13/19 trên 26, thuộc tính 1/10/15,
nên N phải lớn; R@8 văn bản ở N=128 có khoảng tin cậy 0,26 đến 0,61. ITM 0,19 s mỗi ứng viên.

**Đo trực tiếp qua API (cache token 1.523 track đã warm-up, 49 phút, 1,4 GB).** k = 8, 10
lượt: N=64 văn bản p50 9.383 ms, thuộc tính 9.073 ms; N=128 văn bản p50 17.034 ms, thuộc tính
17.110 ms; ảnh không đổi ~1.100 ms. Lần đầu chưa cache thêm ~1,3 s mỗi ứng viên. Phản hồi có
`reranked: true`, điểm 0..1 theo thứ tự ITM.

**Quyết định.** Giữ bước này là tùy chọn (mặc định tắt) vì 17 s mỗi truy vấn trên CPU; khi demo
có thể bật N=64 (9 s) sau khi chạy warm-up. Hướng làm nhanh: tính token ở worker lúc index và
chạy fusion trên GPU (ghi ở 12.3).

**Báo cáo (đã sửa).** 5.2.3 thêm bước 5; 8.2 thêm đoạn "Re-ranking the vector candidates" và
bảng 8.3 mới; 8.3 bảng độ trễ thêm 4 dòng và một đoạn; 12.1, 12.2, 12.3, tóm tắt, 1.4 cập nhật.
`report-data-guide.md` thêm hai dòng C8.4/C8.7. README backend mô tả hai công cụ và biến môi
trường.

**Trạng thái.** Xong 05/10/2026.

### B6. Sửa cách trình bày kết quả và giao thức đo phát hiện

**Báo cáo (đã sửa 05/10/2026, không có mã).**

- Mục 8.2 "Person detection and tracking" viết lại: giao thức (nhãn WILDTRACK là vị trí trên mặt
  đất kèm box mỗi góc nhìn, mỗi khung thứ năm; khớp một-một theo IoU giảm dần, ngưỡng 0,5;
  2.278 box trùng trên người đã khớp), và vì sao precision 0,43 chỉ là cận dưới: nhãn chỉ phủ
  người trong vùng quan tâm của bộ dữ liệu, camera nhìn thấy nhiều người hơn (khung 400: C1
  khoảng 19/30 người có nhãn, C5 3/40, xem ảnh kiểm tra
  `scratchpad/labels-C1.png`, `labels-C5.png` lúc làm). Recall là con số có nghĩa.
- Mục 12.1 điểm 2 "works but with low quality" đã thay ở B5 bằng câu nêu số (R@8 ảnh 0,89;
  văn bản 0 bằng vector, 0,42 khi re-rank 128). Mục 1.4 đã sửa ở B1/B5.

**Trạng thái.** Xong 05/10/2026 (phần nêu nguyên nhân theo bằng chứng của B1/B2 nằm ở 8.2
Discussion, đã viết ở B1 và bổ sung ở B2).

## 4. Nhóm C: pipeline RTSP

### C1. Timestamp khung hình RTSP lấy từ PTS của luồng

**Vấn đề.** `RtspFrameSource._read_source` đặt `source_timestamp_ms` bằng đồng hồ máy trừ gốc
phiên, nên khi xử lý chậm hơn luồng, hai khung được xử lý cách nhau theo thời gian máy chứ không
theo thời gian luồng; quy tắc kết thúc track "hai giây không quan sát" (mục 3.3.5) vì thế cắt track
sớm. Video file không bị vì dùng timestamp ghi trong file.

**Code (đã làm 05/10/2026).** `backend/src/person_search/workers/sources/rtsp.py`:

- `timestamp_mode="stream"` (mặc định): timestamp = mốc neo + (pts - pts neo) x time_base, với mốc
  neo là thời gian máy (so với gốc phiên) tại khung đầu của mỗi phiên RTSP. Mỗi lần `_connect`
  (mở lần đầu hoặc reconnect) xóa neo để phiên mới tự neo lại; pts giảm (nguồn phát lại từ đầu)
  cũng neo lại tại khung đó, mốc neo không nhỏ hơn timestamp cuối. Bảo vệ đơn điệu
  `max(last, new)` giữ nguyên.
- Khung không có pts hoặc time_base dùng đồng hồ máy như cũ và được đếm vào
  `timestamp_fallback_frames` (cảnh báo log một lần); `timeline_anchors` đếm số lần neo;
  `timestamp_mode="clock"` giữ hành vi cũ để đối chứng.
- Mới `backend/tools/rtsp_timestamp_check.py` (mô tả trong README backend).

**Đo (05/10/2026, luồng cam1 của MediaMTX, 300 khung, N = 20, 14 cặp khung lấy mẫu).**

| Xử lý giả lập | Chế độ | Khoảng cách hai khung lấy mẫu theo timestamp (median / max) | Số cặp > 2 s | Theo đồng hồ máy |
| --- | --- | --- | --- | --- |
| 100 ms mỗi khung (chậm ~6 lần) | clock (cũ) | 2,456 / 2,579 ms | 14 / 14 | 2,456 ms |
| 100 ms mỗi khung | stream (mới) | 334 / 334 ms | 0 / 14 | 2,413 ms |
| nhanh nhất có thể | clock (cũ) | 407 / 441 ms | 0 / 14 | 409 ms |
| nhanh nhất có thể | stream (mới) | 334 / 334 ms | 0 / 14 | 404 ms |

334 ms đúng bằng 20 khung ở 60 fps. Nguồn: `var/evidence/rtsp-timestamps-slow100.json`,
`rtsp-timestamps-fast.json`. Không chạy lại phiên RTSP qua worker để khỏi ghi thêm track vào dữ
liệu demo; 35 track RTSP đã có trong dữ liệu demo vẫn mang timestamp theo đồng hồ máy.

**Kiểm thử.** Mới `tests/unit/test_rtsp_stream_timestamps.py` (6 test: theo luồng không theo tốc
độ xử lý, chế độ clock, khung thiếu pts, pts giảm, reconnect, giá trị cờ sai); test cũ trong
`test_rtsp_frame_source.py` vẫn qua vì khung giả không có pts đi đường dự phòng.
`scripts/check.ps1` qua toàn bộ sau khi sửa `test_static_frontend.py` cho độc lập với `.env`.

**Báo cáo (đã sửa).** Mục 3.3.5 gạch "Termination" (cả hai nguồn dùng timestamp trong luồng);
mục 3.7.4 câu về timestamp; mục 8.3 thêm đoạn "Timestamps of RTSP frames" với số đo; mục 12.2 bỏ
câu hạn chế; mục 12.3 bỏ hướng tương lai tương ứng. PDF build lại không lỗi.

**Trạng thái.** Xong 05/10/2026.

### C2. Mã hóa và ghi appearance ngay khi track kết thúc

**Vì sao ưu tiên 3.** Giảm độ trễ từ lúc người xuất hiện đến lúc tìm được (hiện là cuối phiên
1,800 khung), nhưng đòi hỏi tách giai đoạn encode-and-write khỏi cuối job trong
`workers/production.py`, xử lý hủy job giữa chừng (hiện "a job cancelled during analysis writes
nothing", mục 5.2.1) và cập nhật máy trạng thái. Cơ chế ghi outbox đã theo từng appearance nên
phần kho dữ liệu không đổi.

**Báo cáo.** 5.2.1, hình 5.3, 12.2, 12.3.

**Trạng thái.** Chưa làm. Chỉ làm nếu còn thời gian sau toàn bộ ưu tiên 1 và 2.

## 5. E1. Đồng bộ số liệu cuối cùng

Sau khi các task ưu tiên 1 xong: rà lại tóm tắt, "Chapter Summary", mục 1.4, 12.1, 12.2, 12.3 và
slide phần 1 cho khớp số liệu mới (bộ nhớ, bảng 8.2, RTSP). Chạy `latexmk` và kiểm tra không còn
tham chiếu tới số cũ bằng grep các con số "8.0 GiB", "1,978", "4,772", "6 queries", "threshold 0.25".

## 6. Câu trả lời ngắn chuẩn bị cho câu hỏi 8 GB (dùng được ngay cả khi chưa làm xong)

Hệ thống chiếm 8 GiB vì checkpoint RaSa là checkpoint huấn luyện: nó mang bản momentum của cả
hai bộ mã hóa và hàng đợi contrastive, nên mỗi lần nạp tốn 1.9 GiB trong khi suy luận chỉ cần
0.6 đến 0.9 GiB; lúc nạp còn tốn gấp đôi do khởi tạo trọng số ngẫu nhiên rồi mới chép; và mô
hình được nạp hai lần, một ở application server cho truy vấn và một ở worker cho index. Phần còn
lại là runtime torch của từng tiến trình con, Vite dev server và máy ảo Docker. Chỉ nạp đúng
mô-đun cần (A1) và cắt phần nền (A4) đưa tổng xuống khoảng một nửa mà không đổi vector; dùng
chung một bản mã hóa (A2) giảm thêm; lượng tử hóa int8 (A3) là bước tiếp theo nhưng là phiên bản
encoder mới.
