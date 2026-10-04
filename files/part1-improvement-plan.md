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
| B5 | Bật re-rank ITM của RaSa cho truy vấn văn bản và đo | 3 | 1 ngày | B1, B2 |
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

**Đo.** Lặp lại đúng giao thức của mục 8.3 (idle sau warm-up, searching, processing bằng công cụ
chạy pipeline trên video 10 giây) với `tools/measure_stack_memory.py`, lưu
`var/benchmark/stack-memory-after.json`. Mục tiêu: tổng khi đang xử lý không quá 4.5 GiB
(từ 8.0 GiB), application server sau warm-up dưới 1.0 GiB (từ 1,978 MiB).

**Báo cáo.**

- Mục 8.3 "Storage and memory": thay đoạn số liệu bằng một bảng theo thành phần với hai cột
  trước và sau, và một đoạn ngắn nêu bốn nguyên nhân của A0 cùng phần tiết kiệm của mỗi biện pháp.
  Giữ bốn điều kiện đo nhưng viết lại câu cuối (không còn "server and the pipeline load their own
  models" nếu A2 đã làm).
- Mục 12.2 Part I: bỏ hoặc viết lại câu "memory is tight ... about 8 GiB".
- Mục 12.3 Part I: bỏ ý tối ưu bộ nhớ nếu đã làm, giữ hướng GPU và OpenVINO.
- Tóm tắt (abstract) không nêu số bộ nhớ nên không cần sửa.

**Trạng thái.** Chưa làm.

## 3. Nhóm B: chất lượng tìm kiếm bằng văn bản và thuộc tính

### B1. Kiểm chứng đường xử lý văn bản trên miền huấn luyện của RaSa

**Mục đích.** Trả lời "lỗi cài đặt hay domain gap" bằng một thí nghiệm đối chứng: nếu đúng bộ
adapter của ứng dụng (tiền xử lý 384x384 bicubic, chuẩn hóa CLIP, tokenizer BERT, `text_proj`)
đạt kết quả gần số công bố trên dữ liệu cùng miền với CUHK-PEDES, thì đường xử lý đúng và thất
bại trên WILDTRACK là do dữ liệu.

**Code.** `backend/tools/rasa_domain_sanity.py`:

- Gallery: crop người đã cắt sẵn cùng kiểu với CUHK-PEDES. Nguồn ưu tiên là tập test CUHK-PEDES
  nếu đã được cấp; nếu không, dùng các crop Market-1501 và câu mô tả có sẵn của Phần II
  (`notebooks/`, dữ liệu của bạn cùng nhóm) với 200 đến 500 identity, chỉ đọc, không sửa gì ở Phần II.
- Chạy `RasaQueryInferenceGateway.text` cho mỗi câu, `RasaImageEncoder.encode` cho mỗi crop,
  xếp hạng bằng tích vô hướng như `evaluation/wildtrack_eval.rank_gallery`, báo R@1, R@5, R@10.
- Ghi `var/evaluation/rasa-domain-sanity.json` kèm lineage mô hình như các báo cáo đánh giá khác.

**Kỳ vọng.** Trên CUHK-PEDES R@1 gần 76.5%; trên Market-1501 với câu mô tả sinh từ thuộc tính,
R@10 phải cao hơn hẳn mức ngẫu nhiên và hơn CLIP cơ sở của Phần II (33%). Nếu kết quả gần ngẫu
nhiên, dừng lại và tìm lỗi trong adapter trước khi làm B2 trở đi; điểm nghi đầu tiên là
`RasaRuntime.text_embedding` (chế độ `text`, token CLS) và thứ tự kênh màu trong `RasaPreprocessor.image`.

**Báo cáo.** Mục 8.2 thêm đoạn "Pipeline check on the training domain" với một bảng ba dòng.
Mục 3.5.3 câu "this domain gap directly affects text and attribute queries" được dẫn tới bảng này.

**Trạng thái.** Chưa làm.

### B2. Phân tích nguyên nhân thất bại trên WILDTRACK

**Code.** `backend/tools/wildtrack_text_diagnostics.py` chạy trên gallery của B3 và ghi
`var/evaluation/wildtrack-text-diagnostics.json`:

1. Phân bố kích thước crop (chiều cao điểm ảnh) của các track trong gallery so với CUHK-PEDES
   (ảnh cao khoảng 384). Crop nhỏ bị phóng to lên 384x384 là một giả thuyết cần số liệu.
2. Crop tay sát người so với crop tự động nới 5% (mục 5.2.1): với 6 truy vấn hiện có, đo lại R@k
   của tìm bằng văn bản khi gallery dùng crop sát từ nhãn WILDTRACK thay vì crop của pipeline.
   Nếu khác biệt lớn, nguyên nhân nằm ở detector và chọn khung đại diện, không phải ở encoder.
3. Truy vấn màu đơn: "a person wearing a red top", "... a white top", "... black trousers"
   trên gallery, đếm bằng mắt số kết quả đúng màu trong top 16 và lưu ảnh ghép
   (`var/evaluation/color-queries/`). Đây là thứ có thể chiếu khi bảo vệ.
4. Điểm số: phân bố cosine của truy vấn văn bản với toàn gallery (trung bình, độ lệch chuẩn,
   khoảng giữa hạng 1 và hạng 100) để thấy encoder có phân biệt gì trên dữ liệu này không.

**Báo cáo.** Mục 8.2 "Discussion" viết lại: nguyên nhân nêu theo bằng chứng của B1 và B2 thay vì
khẳng định "the main cause is the domain gap". Nếu crop sát cải thiện rõ, mục 12.3 thêm hướng
cải thiện detector và chọn khung đại diện trước khi đổi encoder.

**Trạng thái.** Chưa làm.

### B3. Đo lại ở cấu hình hiện hành và mở rộng bộ truy vấn

**Code.**

- Tạo `files/wildtrack_evaluation_queries_v2.json` cùng schema với bản hiện tại: chọn thêm ít
  nhất 14 `personID` từ `wildtrack-dataset/annotations_positions/` (400 frame có nhãn, 7 camera)
  sao cho mỗi người xuất hiện trên ít nhất 2 camera, ưu tiên đa dạng màu áo, giới tính, vật mang.
  Mỗi truy vấn có ảnh crop từ nhãn, một câu tiếng Anh và bộ thuộc tính, viết tay và được cả hai
  thành viên xem lại. Tổng ít nhất 20 truy vấn.
- `tools/evaluate_wildtrack.py` nhận `--queries` mới; xác nhận ngưỡng detector đọc từ
  `config/ultralytics_yolo_detector.json` hiện hành (0.1). Chạy đủ ba chế độ, ghi
  `var/evaluation/wildtrack-v2-conf010.json`.
- Thêm vào báo cáo JSON khoảng tin cậy Wilson 95% cho mỗi R@k (hàm nhỏ trong
  `evaluation/wildtrack_eval.py`), vì n vẫn nhỏ.

**Báo cáo.**

- Bảng 8.2 thay bằng kết quả mới (n = 20+, ngưỡng 0.1), bỏ hai dòng "Run 1/Run 2" không so sánh
  được; giữ kết quả cũ trong một câu nếu muốn truy vết.
- Mục 8.2 "Method" cập nhật số truy vấn và cách chọn; nêu khoảng tin cậy.
- Mục 12.2 Part I: bỏ câu "the evaluation is incomplete"; 12.3 bỏ ý "measuring search by image
  and by text again".
- Mục 1.4, tóm tắt và chương 12 chỉnh lại câu chữ nếu con số thay đổi về chất.

**Trạng thái.** Chưa làm.

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

**Điều kiện.** Chỉ làm khi B1 cho thấy đường xử lý đúng và B2 cho thấy kết quả đúng nằm trong
top 128 đủ thường xuyên để re-rank có ích. Xung đột với A1: cần `keep_fusion_layers=True`
(thêm khoảng 0.25 GiB).

**Code.** `RasaRuntime.rerank(text, crops)` dùng bộ mã hóa đa thức với `mode="fusion"` và
`itm_head`; `services/searches.py` gọi re-rank trên top `itm_rerank_top_k` khi cờ cấu hình bật;
thêm trường `reranked` vào phản hồi API.

**Đo.** R@k trên bộ B3 có và không re-rank; độ trễ truy vấn văn bản (`benchmark_search_latency.py`).

**Báo cáo.** Mục 3.5.3 câu "Re-ranking is disabled" sửa theo kết quả; 8.2 và 8.4 thêm dòng;
12.3 bỏ hướng tương lai này nếu đã làm.

**Trạng thái.** Chưa làm.

### B6. Sửa cách trình bày kết quả và giao thức đo phát hiện

**Báo cáo (không có mã).**

- Mục 8.2 "Person detection": mô tả giao thức đo precision và recall: box tham chiếu lấy từ
  `annotations_positions` thế nào, khớp ở IoU 0.5, trên những frame có nhãn nào, và
  precision thấp phản ánh gì (người ngoài vùng nhãn, box không khớp, phát hiện sai). Nếu một
  phần precision thấp là do vùng nhãn WILDTRACK hẹp hơn khung hình, nói rõ.
- Mục 12.1 Part I điểm 2: thay "works but with low quality" bằng câu nêu thẳng kết quả theo
  bảng 8.2 mới.
- Mục 1.4 "Search quality depends on existing models": thêm một câu dẫn tới B1 và B2.

**Trạng thái.** Chưa làm.

## 4. Nhóm C: pipeline RTSP

### C1. Timestamp khung hình RTSP lấy từ PTS của luồng

**Vấn đề.** `RtspFrameSource._read_source` trong `backend/src/person_search/workers/sources/rtsp.py`
đặt `source_timestamp_ms` bằng đồng hồ máy trừ gốc phiên, nên khi xử lý chậm hơn luồng, hai
khung được xử lý cách nhau theo thời gian máy chứ không theo thời gian luồng; quy tắc kết thúc
track "hai giây không quan sát" (mục 3.3.5) vì thế cắt track sớm. Video file không bị vì dùng
timestamp ghi trong file.

**Code.**

- Lấy `decoded.pts` và `stream.time_base` của PyAV; `source_timestamp_ms = origin_ms +
  (pts - first_pts) * time_base * 1000`, với `first_pts` neo ở khung đầu của phiên và
  `origin_ms` là thời điểm thực của khung đầu (giữ ý nghĩa "thời gian xuất hiện" cho người dùng).
- Khi `pts` là `None` hoặc giảm (luồng lặp lại từ đầu sau `-stream_loop -1`, hoặc sau reconnect),
  neo lại `first_pts` tại khung đó với `origin_ms` lấy từ đồng hồ, và ghi log một sự kiện.
  Giữ bảo vệ đơn điệu `max(last, new)`.
- Giữ đồng hồ máy làm dự phòng khi luồng không có PTS, ghi vào metrics của job nguồn timestamp
  nào đang dùng.

**Đo.**

- Unit test trong `tests/unit/test_rtsp_frame_source.py`: khung có pts đều, pts thiếu, pts giảm,
  reconnect; khẳng định khoảng cách timestamp không phụ thuộc đồng hồ giả.
- Lặp lại phép thử "RTSP stream handling" của mục 8.3 với cấu hình hiện hành: số track và số
  track ngắn dưới 2 giây trên cùng 300 và 600 khung trước và sau, ghi
  `var/evidence/rtsp-pts-<ngày>.json` qua `tools/rtsp_evidence.py`.

**Báo cáo.**

- Mục 3.3.5 "Track Life Cycle": sửa gạch đầu dòng "Termination" (bỏ vế "RTSP streams use the
  reception time, so slow processing may end tracks early").
- Mục 3.7.4: sửa câu "Each frame is timestamped with the time the system receives it".
- Mục 8.3 "RTSP stream handling": thêm số track trước và sau.
- Mục 12.2 Part I: bỏ câu về timestamp; mục 12.3 bỏ hướng tương lai tương ứng.

**Trạng thái.** Chưa làm.

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
