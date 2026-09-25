# Kế hoạch thiết kế và hiện thực AI Worker

> Tài liệu này là kế hoạch chi tiết cho các thành phần AI worker và inference phục vụ ứng dụng tìm kiếm người qua camera. Yêu cầu cốt lõi được lấy trực tiếp từ `project_requirements.md`, `usecase_detail.md` và `architect.md`; các quyết định chi tiết về registry, sampling và best-shot được bổ sung sau khi người thực hiện xem xét khuyến nghị kỹ thuật. Đây là kế hoạch con; không được tự mở rộng phạm vi hoặc thay đổi quyết định trong ba tài liệu nguồn. Mỗi task phải được triển khai, kiểm thử và review độc lập trước khi chuyển sang task tiếp theo.

## 1. Mục tiêu

Xây dựng AI worker chạy tách khỏi Flask API, có khả năng:

- Nhận tệp video gắn với một camera logic và xử lý tuần tự trong bản demo.
- Nhận luồng RTSP giả lập bằng cùng pipeline để thử nghiệm tại nhà.
- Lấy mẫu `1/N` frame nguồn trước Detector/Tracker và giữ đúng timeline của nguồn.
- Phát hiện người, theo dõi người thành track và chọn một frame đại diện cho mỗi track.
- Dùng RaSa Image Encoder để tạo một Person Embedding cho mỗi track.
- Dùng cùng checkpoint RaSa cho truy vấn ảnh và truy vấn văn bản tiếng Anh.
- Công bố nhất quán full frame, metadata và embedding sang MinIO, PostgreSQL và Milvus.
- Chỉ cho phép tìm kiếm track đã ở trạng thái sẵn sàng.
- Hỗ trợ bật/tắt AI theo camera, cấu hình Detector/Tracker chung, trạng thái, diagnostics, audit và khả năng phục hồi lỗi.
- Cung cấp bằng chứng chất lượng, hiệu năng và khả năng trình diễn trên 7 video.

## 2. Nguồn yêu cầu và truy vết

| Nguồn | Phạm vi được dùng trong kế hoạch |
| --- | --- |
| `project_requirements.md` | Camera Processing Pipeline, Search Components, dữ liệu track, tiếng Anh, Matching Score và quyền hiển thị. |
| `usecase_detail.md` | UC-04 bật/tắt AI, UC-05 cấu hình mô hình, UC-06 trạng thái, UC-07 diagnostics và UC-09 tìm kiếm. |
| `architect.md` | Worker tách tiến trình, video/RTSP dùng chung pipeline, sampling, track buffer, RaSa, ba kho dữ liệu, máy demo và kế hoạch thử 7 video. |

Ma trận truy vết chính:

| Yêu cầu | Task thực hiện |
| --- | --- |
| Video và RTSP đi qua cùng pipeline | AIW-06, AIW-07, AIW-09, AIW-16 |
| Sampling trước Detector/Tracker | AIW-08, AIW-16, AIW-27 |
| Detector → Tracker → RaSa Image Encoder | AIW-10 đến AIW-16 |
| Một track, một frame đại diện, không lưu crop | AIW-12, AIW-18 |
| RaSa cho stored/query embedding | AIW-13 đến AIW-15 |
| Text và attribute chỉ dùng tiếng Anh | AIW-15 |
| Matching Score chỉ tồn tại trong lượt search | AIW-15, AIW-18, AIW-25 |
| Detector/Tracker cấu hình chung | AIW-03, AIW-19 |
| Bật/tắt AI theo camera | AIW-17, AIW-19 |
| Trạng thái và diagnostics theo thành phần | AIW-21, AIW-22 |
| Track chỉ search được khi dữ liệu nhất quán | AIW-18, AIW-20 |
| Demo tuần tự 7 video | AIW-26, AIW-27, AIW-29 |
| RTSP giả lập có bằng chứng | AIW-09, AIW-28 |

## 3. Các quyết định đã khóa

1. AI worker chạy ở tiến trình riêng; không chạy vòng lặp xử lý video/RTSP trong request Flask.
2. Bản demo ưu tiên tệp video và xử lý tuần tự với worker concurrency bằng `1`.
3. RTSP là đường thử nghiệm tại nhà; không yêu cầu bảy luồng RTSP chạy đồng thời.
4. Tệp video và RTSP chỉ khác adapter đọc frame, sau đó dùng chung pipeline.
5. Frame sampling diễn ra trước Detector và Tracker; thử tối thiểu `N=10` và `N=20`. `N=10` là baseline an toàn ban đầu, không phải giá trị mặc định cuối cùng; giá trị production chỉ được khóa sau benchmark AIW-27.
6. Sampling là cấu hình kỹ thuật của hệ thống. Admin không nhập tùy ý một giá trị `N`; phiên bản đầu hiển thị cấu hình đang dùng ở chế độ chỉ đọc. Nếu sau này cần quyền lựa chọn, Admin chỉ được chọn các preset đã benchmark và allowlist phía server, không gửi raw `N` tùy ý.
7. Detector và Tracker lấy từ **model registry nội bộ**, tức danh mục allowlist do developer/deployment quản lý, áp dụng chung toàn hệ thống. Admin chỉ chọn ID đã đăng ký; không tải model, truyền đường dẫn artifact, chọn adapter tùy ý hoặc huấn luyện model mới.
8. RaSa Image/Text Encoder dùng một checkpoint tương thích cố định trong phiên bản đầu.
9. Tìm kiếm văn bản và bộ lọc thuộc tính chỉ dùng tiếng Anh; không dịch tự động từ tiếng Việt.
10. Mỗi kết quả tìm kiếm đại diện cho một track, không phải từng frame.
11. Mỗi track chỉ lưu một full frame đại diện và bounding box. Frame đại diện được chọn bằng **best-shot selection deterministic** từ tối đa 3 ứng viên tốt nhất trong bộ nhớ; không chọn mặc định frame đầu, frame giữa, bbox lớn nhất hoặc detector confidence cao nhất.
12. Bản đầu dùng cùng representative frame cho ảnh hiển thị và crop tạm đưa vào RaSa Image Encoder. Person crop và các frame ứng viên không được chọn chỉ tồn tại tạm thời trong bộ nhớ rồi phải được giải phóng.
13. Matching Score chỉ có trong response của lượt tìm kiếm, không được persist hoặc đưa vào Case.
14. Confidence và quality score nội bộ của Detector/Tracker/selector không được hiển thị như dữ liệu nghiệp vụ.
15. Track chỉ được đánh dấu `READY` sau khi metadata, full frame và vector đã được công bố nhất quán.
16. Lỗi áp dụng cấu hình mới không được phá cấu hình đang hoạt động hoặc dữ liệu lịch sử.
17. Google Colab với T4 được dùng làm môi trường **batch inference, benchmark và chuẩn bị video demo**, không phải worker online bắt buộc phải kết nối liên tục với Flask trong buổi bảo vệ.
18. Buổi bảo vệ ưu tiên chạy ứng dụng local với dữ liệu đã index trước. Nếu cần chứng minh xử lý thật, chỉ chạy thêm một clip ngắn; phần xử lý đủ 7 video được thực hiện trước và lưu bằng chứng tái lập.
19. Cặp baseline ưu tiên để đưa ứng dụng chạy được là Detector YOLO cỡ nano/small đã pin phiên bản + ByteTrack. BoT-SORT là Tracker thay thế đầu tiên trong registry; YOLOX-S/YOLOX-Tiny + ByteTrack là đường dự phòng nếu dependency hoặc giấy phép Ultralytics không phù hợp. Không đổi model chỉ vì có phiên bản mới hơn khi chưa qua smoke test và benchmark.
20. Track ID chỉ có ý nghĩa trong phạm vi camera/job. Một người xuất hiện lại sau khi track đã timeout tạo track mới; cùng một người ở camera khác cũng là track mới. Phiên bản đầu không thực hiện global identity hoặc cross-camera track merging.
21. Khi EOF, worker flush và hoàn tất các track đã confirmed còn hoạt động. Khi cancel, chỉ các track đã hoàn tất và đã publish nhất quán được giữ; track đang active/chưa hoàn tất bị hủy và giải phóng buffer, không phát sinh kết quả dở dang.

### 3.1. Quy ước model registry

Registry không phải model store công khai hoặc chức năng upload model. Đây là manifest allowlist được đóng gói/cấu hình cùng môi trường triển khai. Mỗi entry Detector/Tracker tối thiểu có:

- ID ổn định và display name cho Admin.
- Adapter kind được code hỗ trợ.
- Model/config artifact path nội bộ và checksum.
- Version, input shape, device/runtime hỗ trợ.
- Person class mapping và preprocessing version đối với Detector.
- Compatibility metadata giữa Detector và Tracker.
- License/provenance của code và model artifact, cùng quyết định cho phép dùng trong phạm vi dự án.
- Trạng thái `available` được xác định bằng preflight trên server.

`ActiveAIConfig` chỉ lưu ID/version đã đăng ký. Worker resolve ID qua registry, kiểm tra artifact/checksum/compatibility rồi mới nạp adapter. Request từ UI/API không được cung cấp Python class, module, URL tải model hoặc đường dẫn filesystem.

### 3.2. Chính sách sampling

- Production không nhận raw `N` từ biểu mẫu Admin.
- AIW-27 được phép override `N` trong môi trường benchmark có kiểm soát để so sánh `N=10`, `N=20` và giá trị bổ sung nếu cần.
- Sau benchmark, hệ thống khóa một default profile. Nếu có nhiều profile, mỗi profile ánh xạ server-side tới một `N` đã kiểm chứng, ví dụ `ACCURACY`, `BALANCED`, `FAST_INDEXING`; tên và tập giá trị cuối cùng chỉ được chốt bằng số đo.
- Processing job luôn snapshot và lưu `sampling_interval` thực tế để kết quả có thể tái lập.
- UI trạng thái cho Admin xem profile và `N` đang hoạt động nhưng không cho sửa raw value.
- Nếu nguồn có FPS khác nhau đáng kể, AIW-27 phải đánh giá thêm cách ánh xạ profile theo target processed FPS; không tự áp một `N` cho mọi nguồn nếu số đo cho thấy chất lượng không tương đương.
- Mô hình “Detector chạy theo interval nhưng Tracker vẫn nhận mọi frame” là hướng tối ưu tương lai. Phiên bản đầu vẫn sampling trước cả Detector và Tracker đúng kiến trúc hiện tại; thay đổi mô hình này phải có benchmark và cập nhật kiến trúc trước khi triển khai.

### 3.3. Chính sách best-shot cho representative frame

Mỗi bbox của một track trên sampled frame là một ứng viên. Selector xử lý theo hai bước:

1. **Hard filter:** loại ứng viên bbox không hợp lệ/quá nhỏ, bị cắt biên nghiêm trọng, quá mờ, track chưa confirmed hoặc có biến động bbox bất thường.
2. **Quality ranking:** xếp hạng deterministic bằng các tín hiệu đã normalize. Công thức khởi đầu để benchmark, chưa phải trọng số chất lượng cuối cùng:

```text
quality =
    0.30 * person_resolution
  + 0.25 * sharpness
  + 0.20 * body_completeness
  + 0.15 * detection_track_stability
  + 0.10 * temporal_preference
  - border_clipping_penalty
  - occlusion_penalty
```

Quy tắc thực hiện:

- Giữ tối đa `K=3` ứng viên có điểm cao nhất cho mỗi track; `K` là cấu hình nội bộ có giới hạn, không phải tùy chọn UI.
- Ưu tiên phần ổn định ở giữa track qua `temporal_preference`, nhưng không mặc định chọn frame giữa.
- Detector confidence chỉ là một thành phần của stability, không tự quyết định frame thắng.
- Tie-break theo quality, sau đó sharpness, person resolution và cuối cùng source frame index nhỏ hơn để kết quả tái lập.
- Nhiều track trên cùng source frame nên dùng shared frame reference/reference counting thay vì nhân bản ảnh không giới hạn.
- Có giới hạn tổng byte toàn buffer; khi vượt giới hạn phải loại ứng viên thấp nhất hoặc kết thúc có lỗi rõ ràng, không để worker OOM.
- Khi track kết thúc, chọn ứng viên tốt nhất, crop tạm để tạo embedding, persist đúng full frame+bbox đã chọn, rồi giải phóng toàn bộ crop/ứng viên còn lại.
- Nếu không ứng viên nào qua hard filter, chọn best available theo fallback có cờ quality nội bộ `LOW`; không công bố kết quả giả và không hiển thị quality score cho người dùng.
- Multi-frame embedding/quality-weighted aggregation là hướng nâng cấp sau baseline. Nó nằm ngoài phiên bản đầu vì thay đổi cách tạo một embedding cho track và phải được đo, review, cập nhật kiến trúc trước khi bật.

### 3.4. Chiến lược chạy local và Google Colab

- **Local là system of record:** Flask API, PostgreSQL, MinIO và Milvus vẫn chạy trong môi trường ứng dụng; dữ liệu đã index local là nguồn dùng cho search/Case trong buổi bảo vệ.
- **Colab T4 là batch runner:** notebook dùng cùng pipeline/contract với worker để xử lý tuần tự 7 video, benchmark Detector/Tracker/RaSa và tạo bằng chứng. Không để buổi bảo vệ phụ thuộc vào việc Colab còn phiên, còn T4 hoặc còn kết nối mạng.
- **Không cho Colab ghi thẳng vào database/storage local qua tunnel.** Batch runner xuất một result bundle có version; importer local kiểm tra bundle rồi gọi đường `TrackPublisher` chuẩn để đưa dữ liệu vào ba kho.
- Result bundle tối thiểu gồm manifest schema version, checksum nguồn, model/config/checkpoint lineage, sampling interval, metadata track dạng JSONL, đúng một full frame+bbox cho mỗi track, embedding và checksum từng artifact. Bundle không chứa person crop, secret hoặc Matching Score.
- `Latest` runtime không được xem là dependency ổn định. Notebook phải pin package/model commit, ghi Python/PyTorch/CUDA/GPU thực tế và chạy preflight. Do RaSa upstream dùng dependency cũ, AIW-04 phải chứng minh đường tương thích trên Colab trước khi xử lý toàn bộ dữ liệu.
- Batch size khởi đầu bằng `1`; chỉ tăng sau khi đo VRAM. Notebook phải checkpoint theo video/job để runtime bị ngắt không buộc chạy lại toàn bộ 7 video.
- Video demo quay trước phải thể hiện rõ phần nào là batch preprocessing đã thực hiện và phần nào là thao tác ứng dụng/search/Case chạy thật; không trình bày video dựng sẵn như một luồng live.

### 3.5. Baseline Detector/Tracker và cơ chế thay thế

Thứ tự triển khai nhằm giảm rủi ro tích hợp, không nhằm tuyên bố model tốt nhất:

1. **Baseline chức năng:** YOLO nano/small đã pin artifact + ByteTrack. WILDTRACK dùng camera tĩnh, nên ByteTrack là điểm bắt đầu ít overhead, không cần ReID và camera-motion compensation.
2. **Tracker thay thế:** BoT-SORT, mặc định tắt ReID; chỉ bật hoặc tune thêm nếu benchmark cho thấy ID switch/occlusion là vấn đề đáng kể. Với camera tĩnh, camera-motion compensation cũng mặc định tắt.
3. **Detector dự phòng giấy phép/dependency:** YOLOX-S hoặc YOLOX-Tiny + ByteTrack. Đường này ưu tiên khi không thể chấp nhận điều kiện AGPL của package/model Ultralytics hoặc khi adapter Ultralytics không ổn định trong môi trường đã pin.

Orchestration không gọi API track end-to-end của một vendor. `DetectorAdapter` chỉ xuất danh sách detection chuẩn hóa `xyxy + score + class_id`; `TrackerAdapter` nhận contract này và xuất `TrackUpdate`. Registry quyết định adapter/artifact/config nào được nạp. Nhờ vậy có thể đổi Detector hoặc Tracker độc lập mà không sửa sampling, best-shot, encoder, publisher hay nghiệp vụ search.

Chỉ một cặp được active toàn hệ thống tại một thời điểm. Cặp mới phải qua preflight, contract test và smoke test trên cùng fixture trước khi được chọn; lỗi activate phải giữ nguyên cặp đang hoạt động.

### 3.6. Vòng đời track đã khóa

- `local_track_id` không được tái sử dụng trong cùng camera/job; `track_id` công bố phải ổn định và duy nhất toàn hệ thống.
- Occlusion ngắn còn trong lost timeout có thể nối lại cùng track. Sau timeout, detection kế tiếp tạo track mới dù có thể là cùng một người.
- Không nối track giữa hai camera và không dùng RaSa embedding để tự động hợp nhất danh tính.
- EOF flush track đã confirmed theo đường hoàn tất bình thường; track chưa confirmed bị loại.
- Cancel không flush active track thành kết quả mới. Chỉ track đã hoàn tất, encode và publish `READY` trước safe point được giữ.
- Lost timeout phải được định nghĩa theo source time và quy đổi rõ theo sampled frame count; không phụ thuộc tốc độ xử lý của máy.

## 4. Ngoài phạm vi

- Huấn luyện hoặc fine-tune Detector, Tracker hay RaSa.
- Hỗ trợ truy vấn văn bản tiếng Việt hoặc dịch tự động.
- Lưu person crop thành object lâu dài.
- Dùng confidence/Matching Score để tự động kết luận danh tính.
- Lưu Matching Score vào PostgreSQL, Milvus, Case hoặc CaseResult.
- Xử lý đồng thời cả 7 camera trong buổi demo.
- Xem Google Colab là worker online phục vụ Flask liên tục.
- Cho Colab truy cập trực tiếp credential PostgreSQL, MinIO hoặc Milvus của môi trường local/demo.
- Tự động thay đổi checkpoint encoder từ giao diện Admin.
- Cho Admin nhập raw sampling interval hoặc thay đổi `N` ngoài preset đã benchmark.
- Multi-frame embedding hoặc persist nhiều representative frame cho một track trong phiên bản đầu.

## 5. Kiến trúc mục tiêu

```text
Flask API / Job Service
          |
          v
  Processing Job Queue
          |
          v
  AI Worker (concurrency = 1)
          |
          +--> FileFrameSource --------+
          |                            |
          +--> RtspFrameSource --------+--> FrameSampler
                                             |
                                             v
                                          Detector
                                             |
                                             v
                                           Tracker
                                             |
                                             v
                                      Bounded Track Buffer
                                             |
                                             v
                                  Representative Frame Selector
                                             |
                                             v
                                    RaSa Image Encoder
                                             |
                                             v
                                      Track Publisher
                                      /      |       \
                               PostgreSQL  MinIO    Milvus

Colab T4 Batch Runner
          |
          v
 Versioned Result Bundle
          |
          v
 Local Bundle Importer --> Track Publisher --> PostgreSQL / MinIO / Milvus

Search request --> Query Inference Gateway --> RaSa Image/Text Encoder
                                             --> query embedding
                                             --> authorized vector search
```

Các adapter production và adapter fake phục vụ test phải dùng chung contract nhưng cấu hình production không được tự động fallback sang fake adapter.

## 6. Hợp đồng dữ liệu tối thiểu

| Contract | Trường tối thiểu |
| --- | --- |
| `SourceFrame` | `camera_id`, `source_frame_index`, `source_timestamp_ms`, `image`, `width`, `height` |
| `SampledFrame` | toàn bộ `SourceFrame`, `sampling_interval`, `sample_sequence` |
| `Detection` | bbox pixel hợp lệ, person class, confidence nội bộ, detector version |
| `TrackUpdate` | local track ID, bbox, frame/timestamp, trạng thái active/ended |
| `RepresentativeCandidate` | frame reference, bbox, quality components, total quality, source frame/timestamp |
| `CompletedTrack` | camera/job/config, start/end, frame đại diện, bbox, quality flag nội bộ, lineage model/sampling |
| `EmbeddingVector` | vector hữu hạn, dimension, normalized flag, encoder/checkpoint version |
| `PublishedTrack` | `track_id`, object key, vector identity, metadata identity, `READY` state |
| `ResultBundleManifest` | schema version, source checksum, model/config/encoder lineage, `N`, danh sách track/artifact và checksum |
| `ComponentStatus` | component, outcome, latency, code an toàn, timestamp |

Quy tắc contract:

- Timestamp nghiệp vụ lấy từ nguồn video/RTSP, không lấy thời điểm worker xử lý thay thế.
- Bounding box phải nằm trong kích thước frame và có diện tích dương.
- Vector phải đúng dimension, không chứa `NaN`/`Inf` và đúng chính sách normalize.
- Không contract nào của Case chứa Matching Score.
- Raw query, credential RTSP, frame hoặc embedding không được ghi vào log.
- Quality components/score chỉ phục vụ selector và diagnostics nội bộ; không thuộc DTO nghiệp vụ hoặc Case.

## 7. Trạng thái task và quy trình theo dõi

Trạng thái hợp lệ:

- `TODO`: chưa bắt đầu.
- `IN_PROGRESS`: đang triển khai; tại một thời điểm chỉ nên có một task trên đường găng ở trạng thái này.
- `BLOCKED`: thiếu quyết định, dữ liệu, checkpoint hoặc môi trường.
- `REVIEW`: code và test đã xong, đang chờ người thực hiện duyệt.
- `DONE`: đã review, test đạt và tài liệu liên quan được cập nhật.

Quy trình cho mỗi task:

1. Chuyển task sang `IN_PROGRESS` và ghi ngày bắt đầu.
2. Chỉ sửa phạm vi đã nêu trong task; phát hiện thay đổi thiết kế phải ghi lại trước khi code.
3. Chạy bộ test được yêu cầu và lưu lệnh/kết quả vào nhật ký thực hiện.
4. Chuyển sang `REVIEW`, tóm tắt file thay đổi, rủi ro và bằng chứng test.
5. Chỉ chuyển `DONE` sau khi được review chấp thuận.
6. Không tự động bắt đầu task kế tiếp khi task hiện tại chưa được duyệt.

## 8. Bảng kế hoạch tổng thể

| ID | Task | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- |
| AIW-00 | Baseline và ma trận truy vết | — | REVIEW |
| AIW-01 | Inventory 7 video và bộ dữ liệu đánh giá | AIW-00 | TODO |
| AIW-02 | Khóa contract và taxonomy lỗi AI | AIW-00 | TODO |
| AIW-03 | Registry Detector/Tracker/Encoder và kiểm tra artifact | AIW-02 | TODO |
| AIW-04 | Runtime/device preflight và giới hạn tài nguyên | AIW-03 | TODO |
| AIW-05 | Fake adapters và fixtures chỉ dành cho test | AIW-02 | TODO |
| AIW-06 | Interface nguồn frame dùng chung | AIW-02 | TODO |
| AIW-07 | File video source production | AIW-06 | TODO |
| AIW-08 | Frame sampling và timeline nguồn | AIW-07 | TODO |
| AIW-09 | RTSP source, reconnect và thử MediaMTX | AIW-06, AIW-08 | TODO |
| AIW-10 | Detector production adapter | AIW-03, AIW-04, AIW-08 | TODO |
| AIW-11 | Tracker production adapter | AIW-03, AIW-10 | TODO |
| AIW-12 | Track buffer và chọn frame đại diện | AIW-11 | TODO |
| AIW-13 | Tích hợp checkpoint và preprocessing RaSa | AIW-03, AIW-04 | TODO |
| AIW-14 | RaSa Image Encoder | AIW-12, AIW-13 | TODO |
| AIW-15 | RaSa query inference: image/text/attribute tiếng Anh | AIW-13 | TODO |
| AIW-16 | Ghép pipeline production hoàn chỉnh | AIW-08, AIW-10 đến AIW-15 | TODO |
| AIW-17 | Worker loop và vòng đời processing job | AIW-16 | TODO |
| AIW-18 | Công bố track nhất quán sang ba kho | AIW-14, AIW-17 | TODO |
| AIW-19 | Bật/tắt AI và áp dụng cấu hình model | AIW-03, AIW-17 | TODO |
| AIW-20 | Retry, idempotency và phục hồi worker | AIW-18, AIW-19 | TODO |
| AIW-21 | Heartbeat, metrics và trạng thái vận hành | AIW-17, AIW-20 | TODO |
| AIW-22 | Diagnostics bằng nguồn/model thật | AIW-15, AIW-16, AIW-21 | TODO |
| AIW-23 | Audit, logging và bảo vệ dữ liệu nhạy cảm | AIW-17 đến AIW-22 | TODO |
| AIW-24 | Test component và failure injection | AIW-16 đến AIW-23 | TODO |
| AIW-25 | E2E một video → search → Case → Viewer | AIW-18, AIW-22, AIW-24 | TODO |
| AIW-26 | Đánh giá chất lượng trên 7 video | AIW-25 | TODO |
| AIW-27 | Benchmark `N=10`/`N=20` và tài nguyên máy demo | AIW-25 | TODO |
| AIW-28 | Bằng chứng xử lý RTSP giả lập | AIW-09, AIW-25 | TODO |
| AIW-29 | Đóng gói, runbook và nghiệm thu AI worker | AIW-26 đến AIW-28 | TODO |

Đường găng cho lát cắt đầu tiên:

```text
AIW-00 → AIW-02 → AIW-03 → AIW-04
                    ├→ AIW-07 → AIW-08 → AIW-10 → AIW-11 → AIW-12
                    └→ AIW-13 → AIW-14
AIW-12 + AIW-14 → AIW-16 → AIW-17 → AIW-18 → AIW-25
```

## 9. Chi tiết từng task

### AIW-00 — Baseline và ma trận truy vết

**Mục tiêu:** xác định chính xác hiện trạng worker và ánh xạ từng yêu cầu sang thành phần cần sửa.

**Phạm vi:**

- Inventory worker entrypoint, pipeline, adapter, job service, ingestion service và diagnostics hiện có.
- Phân loại code thành production-ready, scaffolding, fake/demo và chưa có.
- Xác định các đường chạy có thể vô tình dùng adapter demo.
- Lập ma trận requirement → module → test → bằng chứng.

**Đầu ra:** baseline report, sơ đồ module hiện tại và danh sách gap có mức ưu tiên.

**Kiểm thử/xác minh:** chạy unit test hiện có và một smoke worker demo không ghi dữ liệu production.

**Tiêu chí hoàn thành:** không còn thành phần AI hiện hữu nào chưa được phân loại; phạm vi task sau có file/module đích rõ ràng.

---

### AIW-01 — Inventory 7 video và bộ dữ liệu đánh giá

**Mục tiêu:** biến 7 video thành bộ đầu vào có thể lặp lại cho phát triển và benchmark.

**Phạm vi:**

- Input đã có tại `wildtrack-dataset/`: `cam1.mp4` đến `cam7.mp4`, 400 file annotation position và 401 ảnh 1920×1080 cho mỗi camera `C1` đến `C7`; tổng dung lượng sơ bộ khoảng 10,84 GiB.
- Ghi camera logic, khu vực, codec, độ phân giải, FPS, số frame, thời lượng và kích thước từng video.
- Tạo checksum và manifest; không commit video thật nếu vi phạm dung lượng/quyền riêng tư.
- Quyết định rõ dataset được quản lý bằng local path, download script hay Git LFS. Hiện `wildtrack-dataset/` đã được `.gitignore` loại trừ; tiếp tục không force-add trước khi chốt cách quản lý và điều khoản phân phối.
- Chọn các đoạn ngắn an toàn làm fixture hoặc ghi hướng dẫn tạo fixture cục bộ.
- Xây ground-truth tối thiểu cho người/track/query dùng đánh giá.
- Chuẩn bị tập truy vấn ảnh, câu tiếng Anh và thuộc tính tiếng Anh.

**Đầu ra:** dataset manifest, fixture policy và evaluation query set.

**Kiểm thử/xác minh:** script đọc được đủ manifest và xác nhận checksum/metadata.

**Tiêu chí hoàn thành:** đủ dữ liệu để lặp lại phép thử một video và phép đo tổng hợp 7 video; dữ liệu nhạy cảm không bị stage.

---

### AIW-02 — Khóa contract và taxonomy lỗi AI

**Mục tiêu:** tách model/framework cụ thể khỏi orchestration và chuẩn hóa lỗi.

**Phạm vi:**

- Định nghĩa các contract tại mục 6 bằng type rõ ràng.
- Định nghĩa interface `FrameSource`, `Detector`, `Tracker`, `ImageEncoder`, `TextEncoder`, `TrackSelector` và `TrackPublisher`.
- Chuẩn hóa lifecycle `open/read/flush/close` và ownership tài nguyên.
- Định nghĩa mã lỗi theo stage: source, sampling, detector, tracker, selector, encoder, storage, cancellation và resource exhaustion.
- Phân biệt lỗi retryable và terminal; message public không chứa secret.

**Đầu ra:** module contract, error model và tài liệu sequence.

**Kiểm thử:** contract tests cho bbox, timestamp, vector dimension, `NaN`/`Inf`, close idempotent và error serialization.

**Tiêu chí hoàn thành:** fake và production adapter có thể thay thế qua cùng interface; orchestration không import framework model cụ thể.

---

### AIW-03 — Registry model và kiểm tra artifact

**Mục tiêu:** chỉ cho phép worker nạp Detector/Tracker trong allowlist nội bộ và checkpoint RaSa cố định hợp lệ.

**Phạm vi:**

- Schema registry gồm ID, display name, version, adapter kind được code hỗ trợ, artifact path nội bộ, checksum, device support, input shape và compatibility metadata.
- Compatibility matrix Detector ↔ Tracker.
- Registry khởi đầu có candidate cho YOLO nano/small + ByteTrack, BoT-SORT và đường dự phòng YOLOX-S/YOLOX-Tiny + ByteTrack; chỉ entry qua preflight mới có `available=true`.
- Ghi provenance/license cho package, source và pretrained weight; không khóa Ultralytics thành production dependency nếu phạm vi phát hành của dự án không đáp ứng điều kiện license.
- Encoder metadata gồm checkpoint version, dimension, normalization và preprocessing version.
- Validate registry ngay khi khởi động; không tải model từ URL tùy ý trong request.
- Tách manifest production khỏi manifest demo/test.
- API chỉ nhận ID allowlisted; từ chối adapter class, URL và filesystem path do client cung cấp.
- Preflight tính `available`; Admin không thể tự sửa trạng thái này hoặc thêm registry entry từ UI.

**Đầu ra:** registry schema, loader và manifest production mẫu không chứa secret/artifact lớn.

**Kiểm thử:** artifact thiếu/sai checksum, ID trùng, adapter lạ, dimension sai, cặp Detector/Tracker không tương thích và request cố inject URL/path/class.

**Tiêu chí hoàn thành:** cấu hình sai fail-fast; production không fallback sang synthetic adapter.

---

### AIW-04 — Runtime/device preflight và giới hạn tài nguyên

**Mục tiêu:** xác nhận worker có thể nạp model trên máy demo trước khi nhận job.

**Phạm vi:**

- Phát hiện CPU/iGPU/CUDA runtime khả dụng; CPU là baseline chức năng bắt buộc, Colab T4 là profile batch GPU ưu tiên.
- Kiểm tra RAM/disk trống, model artifact, codec và thư viện native.
- Đo RAM khi idle và sau khi nạp từng model.
- Có compatibility spike cho RaSa trên Colab vì upstream khai báo PyTorch 1.9.1, torchvision 0.10.1, Transformers 4.8.1 và timm 0.4.9, không mặc định tương thích với runtime `Latest`.
- Ghi chính xác Python, PyTorch, CUDA, GPU, package lock, model checksum và kết quả `nvidia-smi` trong report; notebook setup phải idempotent sau khi runtime reset.
- Cấu hình thread, timeout, batch size và giới hạn buffer an toàn.
- Chỉ đánh giá OpenVINO sau khi baseline đúng; không tối ưu trước khi có số đo.

**Đầu ra:** preflight command/report và cấu hình tài nguyên mặc định.

**Kiểm thử:** thiếu artifact, thiếu codec, RAM/disk dưới ngưỡng cấu hình và runtime không hỗ trợ.

**Tiêu chí hoàn thành:** worker từ chối nhận job với lỗi thành phần rõ ràng thay vì crash/OOM khó truy vết.

---

### AIW-05 — Fake adapters và fixtures chỉ dành cho test

**Mục tiêu:** giữ test nhanh, deterministic mà không gây nhầm với AI thật.

**Phạm vi:**

- Đưa fake detector/tracker/encoder vào namespace test/demo rõ ràng.
- Gắn cờ output synthetic trong test-only metadata.
- Cấm production manifest tham chiếu fake adapter.
- Tạo fixture có bbox/track/vector đã biết để test orchestration và storage.

**Đầu ra:** test adapter package và guard chống bật nhầm production.

**Kiểm thử:** production startup với fake registry phải fail; test profile vẫn chạy được offline.

**Tiêu chí hoàn thành:** mọi test không cần model thật vẫn deterministic, nhưng không có đường silent fallback trong production.

---

### AIW-06 — Interface nguồn frame dùng chung

**Mục tiêu:** thống nhất đầu ra từ tệp video và RTSP.

**Phạm vi:**

- Interface iterator/context manager trả `SourceFrame`.
- Chính sách màu ảnh, orientation, timestamp, frame index và end-of-stream.
- Cancellation và close phải giải phóng decoder/socket.
- Không đọc toàn video vào RAM.

**Đầu ra:** `FrameSource` contract và shared decoder utilities.

**Kiểm thử:** nguồn rỗng, frame hỏng, cancellation, close nhiều lần và timestamp không giảm.

**Tiêu chí hoàn thành:** pipeline phía sau không cần biết frame đến từ FILE hay RTSP.

---

### AIW-07 — File video source production

**Mục tiêu:** đọc ổn định các video demo theo camera logic.

**Phạm vi:**

- Decode video streaming, lấy FPS/time base/frame count khi có.
- Tính timestamp nguồn bằng PTS; fallback có kiểm soát khi metadata thiếu.
- Kiểm tra chữ ký, codec, kích thước và giới hạn video trước xử lý.
- Báo progress dựa trên frame/time khi có thể.
- Phân biệt EOF hợp lệ với decoder failure.

**Đầu ra:** `FileFrameSource` production và probe metadata.

**Kiểm thử:** các codec fixture, FPS biến đổi, metadata thiếu, frame hỏng giữa luồng, file bị thay đổi và cancel.

**Tiêu chí hoàn thành:** đọc tuần tự một video thật mà RAM không tăng theo độ dài video; timeline có thể truy vết về frame nguồn.

---

### AIW-08 — Frame sampling và timeline nguồn

**Mục tiêu:** lấy đúng một frame trong mỗi `N` frame trước Detector/Tracker.

**Phạm vi:**

- Khóa quy tắc frame đầu tiên và công thức chọn frame theo index.
- Giữ `source_frame_index`, `source_timestamp_ms`, `sample_sequence` và `N`.
- Tracker nhận khoảng thời gian thật hoặc sample sequence theo contract đã chọn; không coi frame bị bỏ qua là frame tracker đã xử lý.
- Hỗ trợ tối thiểu `N=10` và `N=20`.
- Dùng `N=10` làm baseline đầu tiên; không khóa default production trước AIW-27.
- Tách nguồn cấu hình production profile khỏi benchmark override.
- Không expose raw `N` như trường Admin có thể nhập tùy ý; job vẫn snapshot `N` thực tế.

**Đầu ra:** `FrameSampler` thuần, deterministic.

**Kiểm thử:** video ngắn hơn N, index boundary, timestamp biến đổi, N không hợp lệ, N=10/N=20, profile mapping, từ chối raw Admin override và cancellation.

**Tiêu chí hoàn thành:** Detector/Tracker không được gọi trên frame bị bỏ qua; số frame mẫu và timestamp đúng fixture; production chỉ dùng profile/default đã allowlist trong khi benchmark override bị cô lập.

---

### AIW-09 — RTSP source, reconnect và thử MediaMTX

**Mục tiêu:** chứng minh nguồn RTSP đi qua cùng pipeline với nguồn file.

**Phạm vi:**

- `RtspFrameSource` dùng credential an toàn và timeout hữu hạn.
- Chống SSRF theo policy backend; không log URL chứa credential.
- Phân biệt connect timeout, auth failure, read timeout và stream ended.
- Reconnect với backoff, giới hạn lần thử và cancellation ngay lập tức.
- Chuẩn bị MediaMTX + FFmpeg recipe để phát một video fixture thành RTSP.

**Đầu ra:** RTSP adapter, test harness và hướng dẫn local.

**Kiểm thử:** stream tốt, sai credential, host bị chặn, mất stream, reconnect, cancel khi chờ và leak socket.

**Tiêu chí hoàn thành:** cùng một pipeline xử lý được fixture file và bản RTSP của fixture; lỗi nguồn không tạo track giả.

---

### AIW-10 — Detector production adapter

**Mục tiêu:** phát hiện người thật trên sampled frame.

**Phạm vi:**

- Implement adapter đầu tiên cho YOLO nano/small đã pin phiên bản/artifact; model cụ thể chỉ được active sau smoke test local và Colab T4.
- Giữ YOLOX-S/YOLOX-Tiny là adapter dự phòng có phạm vi rõ; không implement đồng thời nếu baseline YOLO đã đạt và license phù hợp.
- Preprocess, inference, NMS và chuyển bbox về pixel frame gốc.
- Chỉ chuyển person class sang Tracker.
- Confidence chỉ dùng nội bộ và không đi vào response nghiệp vụ.
- Timeout và giải phóng tensor/buffer sau mỗi frame.

**Đầu ra:** production detector adapter và model-specific config.

**Kiểm thử:** không có người, một/nhiều người, bbox biên, frame kích thước khác nhau, timeout và output model sai shape.

**Tiêu chí hoàn thành:** detector tạo bbox hợp lệ trên fixture thật, không dùng synthetic central box và có số đo latency.

---

### AIW-11 — Tracker production adapter

**Mục tiêu:** nối detection thành track ổn định trên các frame đã sampling.

**Phạm vi:**

- Implement ByteTrack làm baseline đầu tiên; thêm BoT-SORT như registry alternative sau khi ByteTrack chạy end-to-end.
- Mapping detection → tracker input và tracker output → `TrackUpdate`.
- ID chỉ có ý nghĩa trong phạm vi camera/job; worker tạo `track_id` toàn cục khi hoàn tất.
- Chốt timeout kết thúc track theo thời gian thật/sample count.
- Reappearance sau timeout và cùng người ở camera khác đều tạo track mới; không cross-camera/global identity merge.
- Flush track đã confirmed ở EOF; cancel không biến active track thành completed track mới.

**Đầu ra:** production tracker adapter và lifecycle contract.

**Kiểm thử:** người vào/ra khung hình, occlusion ngắn, nhiều người giao nhau, frame gap do sampling, EOF và reset giữa job.

**Tiêu chí hoàn thành:** không rò state từ camera/job trước; completed track có start/end timestamp hợp lệ.

---

### AIW-12 — Track buffer và chọn frame đại diện

**Mục tiêu:** giữ dữ liệu ứng viên có giới hạn và chọn một full frame+bbox tốt cho mỗi track.

**Phạm vi:**

- Buffer giữ tối đa `K=3` ứng viên mỗi track và có giới hạn tổng byte, không giữ toàn bộ frame của track.
- Hard filter loại bbox không hợp lệ/quá nhỏ, clipping nghiêm trọng, blur quá mức, track chưa confirmed và bbox bất ổn.
- Quality score deterministic theo mục 3.3, xét person resolution, sharpness, body completeness, detector/track stability, temporal preference và penalty clipping/occlusion.
- Detector confidence không được dùng làm tiêu chí duy nhất; frame đầu/giữa/cuối và bbox lớn nhất cũng không được mặc định là representative.
- Tie-break ổn định và shared frame reference/reference counting khi nhiều track dùng cùng source frame.
- Sao chép/giữ ownership frame an toàn; giải phóng ngay ứng viên không còn cần.
- Crop tạm thời có clamp/padding xác định, nhưng không persist crop.
- Flush và cleanup khi track kết thúc, job cancel hoặc lỗi.
- Fallback best-available có quality flag nội bộ `LOW` nếu không candidate nào qua hard filter.

**Đầu ra:** `TrackBuffer` và `RepresentativeFrameSelector`.

**Kiểm thử:** track dài, bbox ngoài biên/quá nhỏ, frame mờ, người bị cắt biên, confidence cao nhưng ảnh xấu, top-3 replacement, shared frame reference, tie-break deterministic, fallback `LOW`, pressure bộ nhớ, cancel và cleanup.

**Tiêu chí hoàn thành:** mỗi completed track có đúng một frame đại diện+bbox được chọn bằng cùng thuật toán deterministic; RAM bị chặn bởi giới hạn cấu hình; các ứng viên còn lại được giải phóng.

---

### AIW-13 — Tích hợp checkpoint và preprocessing RaSa

**Mục tiêu:** nạp đúng checkpoint RaSa và khóa không gian embedding.

**Phạm vi:**

- Chọn checkpoint dành cho person text-image retrieval và ghi license/provenance/checksum.
- Tái tạo tokenizer, image transform, input size, normalization và model config đúng checkpoint.
- Xác định embedding dimension và chính sách L2 normalization.
- Xác định API feature extraction cho image/text và khả năng image–text matching/rerank.
- Không cho trộn vector từ encoder version khác trong cùng truy vấn.

**Đầu ra:** RaSa runtime factory, preprocessing module và model card nội bộ.

**Kiểm thử:** checkpoint thiếu/sai checksum, preprocess snapshot, dimension, vector finite, deterministic tolerance và version mismatch.

**Tiêu chí hoàn thành:** cùng checkpoint tạo được image/text embedding hợp lệ trên máy demo hoặc môi trường đã phê duyệt.

---

### AIW-14 — RaSa Image Encoder

**Mục tiêu:** dùng cùng image encoder cho stored track và query image.

**Phạm vi:**

- Encode crop tạm của frame đại diện thành Person Embedding.
- Encode ảnh crop do Operator tải lên thành Query Embedding.
- Dùng chung preprocessing/version/dimension/normalization.
- Validate ảnh, channel, orientation và giới hạn kích thước trước inference.
- Không persist crop hoặc raw query image mặc định.
- Xác nhận frame dùng tạo Person Embedding chính là full frame+bbox được persist để ảnh hiển thị và embedding có cùng lineage.
- Không aggregate nhiều frame trong phiên bản đầu.

**Đầu ra:** production `RaSaImageEncoder` và adapter cho pipeline/query gateway.

**Kiểm thử:** ảnh hợp lệ/hỏng/quá lớn, RGB/grayscale, dimension, vector finite, timeout và so sánh cùng ảnh trong tolerance.

**Tiêu chí hoàn thành:** stored embedding và query image embedding nằm trong cùng không gian, có version lineage và không dùng hash giả.

---

### AIW-15 — RaSa query inference cho image/text/attribute tiếng Anh

**Mục tiêu:** tạo Query Embedding thật cho ba mode tìm kiếm.

**Phạm vi:**

- Query image gọi adapter AIW-14.
- Text Encoder chỉ nhận mô tả tiếng Anh theo contract; không dịch tự động.
- Attribute schema có tên/giá trị tiếng Anh và prompt builder deterministic bằng tiếng Anh.
- Cùng checkpoint/version/dimension với vector đã index.
- Đánh giá tùy chọn rerank image–text; chỉ bật nếu có bằng chứng cải thiện và đủ tài nguyên.
- Matching Score chỉ được trả cho lượt search, không persist.

**Đầu ra:** query inference gateway, English prompt builder và version checks.

**Kiểm thử:** text rỗng/quá dài/ngoài contract, attribute lạ/conflict, prompt snapshot, image/text dimension, version mismatch, timeout và xác nhận không persist raw query/score.

**Tiêu chí hoàn thành:** ba mode sinh query vector thật; thuộc tính luôn sinh prompt tiếng Anh; không có field score trong Case contract.

---

### AIW-16 — Ghép pipeline production hoàn chỉnh

**Mục tiêu:** chạy luồng source → sample → detect → track → select → encode bằng adapter thật.

**Phạm vi:**

- Dependency injection từ registry, không hard-code model trong orchestration.
- Stage timing, cancellation và cleanup bằng `try/finally`.
- Flush tracker/buffer ở EOF theo policy mục 3.6; khi cancel chỉ giữ track đã `READY`, không công bố active track hoặc track chưa encode xong.
- Giới hạn timeout từng stage và timeout toàn job.
- Không fallback sang fake adapter khi stage thật lỗi.

**Đầu ra:** production pipeline factory và runner.

**Kiểm thử:** happy path, zero detection, model load failure, inference failure từng stage, cancel, EOF, timeout và resource cleanup.

**Tiêu chí hoàn thành:** một video fixture tạo completed track có embedding thật; lỗi được gắn đúng stage.

---

### AIW-17 — Worker loop và vòng đời processing job

**Mục tiêu:** xử lý job tuần tự, có lease, progress và graceful shutdown.

**Phạm vi:**

- Claim tối đa một job hợp lệ tại một thời điểm.
- Snapshot camera, area, AI config, encoder version, `N` và timeline origin trước chạy.
- State machine `PENDING → RUNNING → SUCCEEDED/FAILED/CANCELLED`.
- Lease/heartbeat được gia hạn trong quá trình decode/inference dài.
- Progress phân biệt source frames, sampled frames, completed/published tracks.
- SIGTERM/SIGINT ngừng nhận job, cleanup và để job có thể phục hồi.

**Đầu ra:** production worker entrypoint và job runner.

**Kiểm thử:** queue nhiều job, single concurrency, lease expiry, cancel, shutdown giữa job, job không hợp lệ và camera retired.

**Tiêu chí hoàn thành:** bảy job có thể chạy tuần tự; không có hai worker cùng xử lý một job khi dùng cơ chế lock đã chọn.

---

### AIW-18 — Công bố track nhất quán sang ba kho

**Mục tiêu:** bảo đảm track chỉ search được khi PostgreSQL, MinIO và Milvus nhất quán.

**Phạm vi:**

- Tạo track `PENDING` với lineage camera/job/config/model/encoder/`N`.
- Lưu đúng một full frame đại diện vào bucket ứng dụng private.
- Upsert vector và filter fields vào collection/alias đúng encoder version.
- Chuyển `READY` chỉ sau khi xác nhận artifact và vector.
- Dùng outbox/reconciliation hiện có nếu phù hợp; không tự tạo đường ghi song song bỏ qua invariant.
- Thêm `BundlePublisher` cho Colab/batch và local bundle importer. Importer phải xác minh schema/checksum/lineage/idempotency rồi đi qua cùng invariant của `TrackPublisher`, không ghi trực tiếp tùy ý vào ba kho.
- Không lưu crop, Detector confidence hoặc Matching Score.

**Đầu ra:** `TrackPublisher` production và transaction/reconciliation integration.

**Kiểm thử:** PostgreSQL/MinIO/Milvus lỗi tại từng điểm, duplicate publish, retry, object/vector thiếu, encoder mismatch và cleanup an toàn.

**Tiêu chí hoàn thành:** search không thấy track dở dang; retry không sinh track trùng ngoài policy.

---

### AIW-19 — Bật/tắt AI và áp dụng cấu hình model

**Mục tiêu:** thực thi đúng UC-04 và UC-05 ở worker runtime.

**Phạm vi:**

- Camera tắt AI hoặc retired không nhận/tạo dữ liệu mới.
- Chốt policy job file đang chạy khi Admin tắt AI: graceful cancel tại safe point.
- Detector/Tracker config là global, versioned và compatibility-checked.
- Track đang hoạt động hoàn tất theo config snapshot cũ; track/job mới dùng config mới.
- Nạp config mới thất bại phải giữ config hoạt động trước đó.
- Encoder cố định, không đưa vào lựa chọn Admin.
- Sampling profile/default thuộc cấu hình kỹ thuật; Admin chỉ xem và, nếu chức năng preset được duyệt sau benchmark, chỉ chọn ID preset allowlisted. API không nhận raw `N` tùy ý từ Admin.

**Đầu ra:** config apply coordinator và worker config cache có version.

**Kiểm thử:** toggle trước/sau claim, toggle giữa job, config race, incompatible pair, load failure, rollback, sampling preset hợp lệ và raw `N` injection.

**Tiêu chí hoàn thành:** không có track trộn lineage model; dữ liệu lịch sử không bị xóa khi tắt AI/retire camera.

---

### AIW-20 — Retry, idempotency và phục hồi worker

**Mục tiêu:** phục hồi có kiểm soát sau crash hoặc dependency outage.

**Phạm vi:**

- Phân loại retryable/terminal theo taxonomy AIW-02.
- Retry có backoff và giới hạn; không retry vô hạn model/input lỗi.
- Job lease hết hạn được reclaim an toàn.
- Publication dùng stable identity/idempotency key để tránh nhân đôi.
- Reconciliation cho track `PENDING`, outbox lỗi, object/vector thiếu.
- Dead-letter/report cho lỗi cần can thiệp.

**Đầu ra:** recovery policy, retry coordinator và reconciliation command.

**Kiểm thử:** kill worker ở từng stage, restart, outage từng storage, duplicate delivery và retry exhaustion.

**Tiêu chí hoàn thành:** sau recovery, track hợp lệ về `READY` hoặc ở trạng thái lỗi rõ ràng; không có kết quả giả hoặc dữ liệu Case bị xóa.

---

### AIW-21 — Heartbeat, metrics và trạng thái vận hành

**Mục tiêu:** cung cấp dữ liệu thật cho UC-06.

**Phạm vi:**

- Worker heartbeat độc lập với trạng thái job.
- Metrics theo camera/job: source FPS, sampled FPS, detector/tracker/encoder latency, queue time, track count, error count, RAM/CPU.
- Trạng thái camera/RTSP/AI/job/component có timestamp và freshness.
- Giới hạn label cardinality; không đưa credential/query/raw frame vào metric.
- API monitoring đọc snapshot an toàn, không gọi inference nặng.

**Đầu ra:** heartbeat/metric reporter và status aggregation contract.

**Kiểm thử:** worker idle/running/dead, stale heartbeat, metric reset, job failure và camera không có RTSP.

**Tiêu chí hoàn thành:** Admin phân biệt được idle, running, queued, disabled, disconnected và error bằng dữ liệu thật.

---

### AIW-22 — Diagnostics bằng nguồn và model thật

**Mục tiêu:** thực thi UC-07 mà không dùng synthetic frame để tuyên bố AI production hoạt động.

**Phạm vi:**

- Camera Pipeline diagnostic lấy frame thật từ camera RTSP được chọn.
- Chạy lần lượt source → Detector → Tracker smoke → Image Encoder và trả kết quả từng bước.
- Không có người là trạng thái `INCONCLUSIVE`, không phải model failure.
- Search Components diagnostic chạy Image Encoder trên fixture an toàn và Text Encoder với câu tiếng Anh cố định.
- Timeout, cleanup và rate limit; không persist output diagnostic thành track nghiệp vụ.

**Đầu ra:** diagnostic runner production và DTO kết quả theo component.

**Kiểm thử:** source lỗi, không có người, từng model lỗi, timeout, success và xác nhận không ghi track/vector.

**Tiêu chí hoàn thành:** kết quả chỉ báo `PASSED` khi adapter production thật chạy thành công; lỗi chỉ đúng component.

---

### AIW-23 — Audit, logging và bảo vệ dữ liệu nhạy cảm

**Mục tiêu:** có khả năng truy vết kỹ thuật mà không làm lộ dữ liệu.

**Phạm vi:**

- Structured log có request/job/camera/config/track correlation ID.
- Audit lỗi quan trọng của RTSP/pipeline và thay đổi cấu hình AI theo yêu cầu.
- Redact RTSP credential, signed URL, raw query, raw embedding và nội dung frame.
- Error public ổn định; stack trace chỉ ở log nội bộ.
- Không audit từng lượt tìm kiếm nghiệp vụ trong phiên bản hiện tại.

**Đầu ra:** logging context, redaction filter và audit event mapping.

**Kiểm thử:** log injection, credential URL, exception model/storage, concurrent jobs và secret scan.

**Tiêu chí hoàn thành:** có thể truy vết một job end-to-end bằng ID mà không thấy secret hoặc dữ liệu sinh trắc thô trong log.

---

### AIW-24 — Test component và failure injection

**Mục tiêu:** tạo test suite chống regression cho toàn bộ AI worker.

**Phạm vi:**

- Unit test contract, sampling, bbox, buffer, selector, prompt và state machine.
- Adapter contract test dùng fixture/fake; smoke model thật gắn marker riêng.
- Integration test với PostgreSQL, MinIO và Milvus disposable.
- Failure injection cho decoder, từng model, storage, lease và cancellation.
- Test memory/resource cleanup lặp nhiều job.

**Đầu ra:** test matrix và lệnh chạy nhanh/đầy đủ/model-real.

**Kiểm thử:** chính là test suite; ghi thời gian và yêu cầu môi trường từng nhóm.

**Tiêu chí hoàn thành:** test nhanh chạy offline; test integration/model-real được tách marker và có hướng dẫn tái lập.

---

### AIW-25 — E2E một video → search → Case → Viewer

**Mục tiêu:** chứng minh lát cắt nghiệp vụ hoàn chỉnh bằng AI thật.

**Phạm vi:**

1. Admin tạo/chọn camera và bật AI.
2. Upload một video, worker xử lý bằng Detector/Tracker/RaSa thật.
3. Track đạt `READY` với frame, bbox và vector.
4. Operator tìm bằng ảnh, text tiếng Anh và attribute tiếng Anh trong đúng area.
5. Kết quả có Matching Score trong lượt search.
6. Operator lưu track vào Case.
7. Operator/Viewer xem crop/full frame+bbox nhưng không thấy Matching Score trong Case.

**Đầu ra:** E2E test/runbook và bộ bằng chứng kết quả.

**Kiểm thử:** happy path, area isolation, storage/model failure và score non-persistence.

**Tiêu chí hoàn thành:** toàn bộ lát cắt chạy qua API/service thật; không seed trực tiếp track để bỏ qua worker.

---

### AIW-26 — Đánh giá chất lượng trên 7 video

**Mục tiêu:** đo chất lượng thực tế thay vì tuyên bố theo cảm tính.

**Phạm vi:**

- Chạy pipeline tuần tự trên đủ 7 video theo manifest; có thể chạy trên Colab T4 nhưng kết quả phải xuất bundle/report tái lập và import local bằng đường chuẩn.
- Tận dụng annotation WILDTRACK hiện có để tạo ground-truth/evaluation subset; không giả định annotation identity đồng nghĩa với track identity nghiệp vụ xuyên camera.
- Đếm detection/track, track đứt, track trùng và trường hợp bỏ sót trên ground-truth mẫu.
- Đánh giá image→image, English text→image và English attribute→image.
- Báo Recall@4/8/12/16 hoặc metric phù hợp cùng ví dụ thành công/thất bại.
- So sánh có/không rerank nếu AIW-15 triển khai thử.

**Đầu ra:** quality report, query set version và artifact bằng chứng.

**Kiểm thử/xác minh:** phép đo có script tái lập, seed/config/checkpoint/version được ghi đầy đủ.

**Tiêu chí hoàn thành:** có baseline định lượng cho cả ba mode. Ngưỡng chấp nhận cuối cùng phải được người thực hiện review; không tự bịa ngưỡng nếu tài liệu nguồn chưa quy định.

---

### AIW-27 — Benchmark `N=10`/`N=20` và tài nguyên máy demo

**Mục tiêu:** chọn sampling/config có bằng chứng trên máy demo.

**Phạm vi:**

- Cùng video/config chạy ít nhất `N=10` và `N=20`.
- Đo riêng profile local CPU/iGPU và Colab T4; ghi loại GPU thực nhận, VRAM, runtime version và compute mode.
- Đo wall time, source/sampled FPS, latency từng stage, peak RAM/CPU/VRAM, disk, số track và track đứt.
- Đo thời gian publication và search latency sau index.
- Kiểm tra toàn stack không OOM với worker concurrency `1`.
- Chọn N mặc định và ghi trade-off; có thể khác giữa thí nghiệm nhưng job phải lưu N.
- Dùng `N=10` làm baseline so sánh đầu tiên, không mặc định coi `N=20` nhanh hơn là tốt hơn.
- Nếu FPS nguồn khác nhau đáng kể, đo thêm profile theo target processed FPS và quyết định dùng fixed N hay mapping theo FPS.
- Nếu cần nhiều chế độ vận hành, chỉ đề xuất preset khi mỗi preset có kết quả chất lượng/tài nguyên và phạm vi dùng rõ ràng.

**Đầu ra:** benchmark report, config mặc định được đề xuất và bảng preset allowlist nếu thực sự cần nhiều profile.

**Kiểm thử/xác minh:** chạy lặp, ghi warm-up/cold-start và phiên bản môi trường.

**Tiêu chí hoàn thành:** lựa chọn N/config demo dựa trên số đo và được review; production không cho Admin nhập raw `N`; bottleneck và giới hạn được công khai.

---

### AIW-28 — Bằng chứng xử lý RTSP giả lập

**Mục tiêu:** chứng minh adapter RTSP hoạt động trên pipeline thật tại nhà.

**Phạm vi:**

- Dùng FFmpeg phát video fixture/thật phù hợp vào MediaMTX.
- Worker đọc RTSP, sampling, detect, track, encode và publish.
- Thử mất kết nối/reconnect và dừng AI.
- Lưu cấu hình đã redact, log, metric, ảnh chụp/video màn hình và kết quả tìm kiếm.

**Đầu ra:** RTSP experiment report và evidence manifest.

**Kiểm thử/xác minh:** ít nhất một happy path và một reconnect path tái lập được.

**Tiêu chí hoàn thành:** bằng chứng cho thấy RTSP và file dùng chung pipeline; không cần chứng minh 7 luồng đồng thời.

---

### AIW-29 — Đóng gói, runbook và nghiệm thu AI worker

**Mục tiêu:** bảo đảm có thể dựng lại và trình diễn ổn định.

**Phạm vi:**

- Khóa dependency/model artifact/checksum và cấu hình environment.
- Có `requirements`/lock riêng cho Colab batch nếu khác runtime local; notebook không phụ thuộc ngầm vào package có sẵn của runtime `Latest`.
- Quy trình start: storage → migrate/seed → inference/model preflight → worker → API.
- Runbook xử lý tuần tự 7 video, chuẩn bị dữ liệu trước và demo thêm một video.
- Runbook buổi bảo vệ dùng dữ liệu đã index local và video demo quay trước; Colab/T4 là tùy chọn bổ sung, không nằm trên critical path.
- Runbook export result bundle trên Colab, kiểm tra checksum, tải về và import local idempotent.
- Runbook restart/cancel/reconcile/backup và xử lý lỗi thường gặp.
- Checklist dung lượng, model license, secret, log và dữ liệu riêng tư trước demo.
- Tổng hợp bằng chứng AIW-25 đến AIW-28.

**Đầu ra:** deployment/runbook, acceptance report và release checklist.

**Kiểm thử:** dựng môi trường sạch, chạy preflight, E2E smoke, restart giữa job và chạy lại search/Case.

**Tiêu chí hoàn thành:** người khác có thể làm theo runbook để chạy demo; không còn adapter fake trên đường production; mọi tiêu chí nghiệm thu bên dưới đạt hoặc được ghi ngoại lệ đã duyệt.

## 10. Definition of Done chung

Một task chỉ được đánh dấu `DONE` khi:

- Phạm vi và tiêu chí chấp nhận của task đã hoàn tất.
- Có unit/integration/smoke test tương xứng và kết quả được ghi lại.
- Không làm suy yếu authorization, area filtering hoặc bảo mật media/credential.
- Không persist crop, Detector confidence hoặc Matching Score trái quy định.
- Không thêm đường production fallback sang fake adapter.
- Error có mã/stage rõ ràng và không làm lộ secret.
- Resource được đóng khi success, failure, timeout và cancellation.
- Tài liệu, registry, cấu hình mẫu và runbook liên quan được cập nhật.
- Diff đã được người thực hiện review và chấp thuận trước task tiếp theo.

## 11. Cổng nghiệm thu theo giai đoạn

### Gate A — Nền tảng sẵn sàng

- AIW-00 đến AIW-05 `DONE`.
- Contract/registry ổn định, production không dùng fake.
- Checkpoint/model artifact có provenance và checksum.

### Gate B — Pipeline một video

- AIW-06 đến AIW-18 `DONE` cho đường file.
- Một video thật tạo track `READY` bằng model thật.
- Không lưu crop, score hoặc confidence nghiệp vụ.

### Gate C — Vận hành an toàn

- AIW-19 đến AIW-24 `DONE`.
- Toggle/config/recovery/heartbeat/diagnostics hoạt động.
- Failure injection không làm xuất hiện track dở dang trong search.

### Gate D — Nghiệp vụ end-to-end

- AIW-25 `DONE`.
- Ba mode search dùng inference thật.
- Matching Score có trong search và không có trong Case.

### Gate E — Sẵn sàng demo

- AIW-26 đến AIW-29 `DONE`.
- Có báo cáo 7 video, benchmark N, bằng chứng RTSP và runbook tái lập.

## 12. Nhật ký thực hiện

Mỗi lần hoàn tất hoặc review task, thêm một dòng; không sửa lịch sử cũ.

| Ngày | Task | Trạng thái mới | Commit/PR | Test đã chạy | Kết quả và ghi chú review |
| --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | Chưa bắt đầu triển khai theo kế hoạch này. |
| 2026-09-25 | AIW-00 | IN_PROGRESS | — | Đang thực hiện | Bắt đầu inventory worker/pipeline/adapter/job/ingestion/diagnostics và ma trận truy vết. |
| 2026-09-25 | AIW-00 | REVIEW | — | `pytest -m unit`; smoke in-memory; `ruff check .`; `compileall` | Baseline report và ma trận truy vết hoàn tất; 324 unit test đạt, smoke worker không ghi production đạt. Chờ review trước khi chuyển `DONE`. |

## 13. Rủi ro cần theo dõi

| Rủi ro | Dấu hiệu | Cách xử lý trong kế hoạch |
| --- | --- | --- |
| RaSa khó chạy trên máy demo | OOM, latency quá cao, thiếu dependency | AIW-04, AIW-13, AIW-27; CPU baseline trước, tối ưu sau khi đúng. |
| RaSa upstream không tương thích Colab `Latest` | Lỗi cài PyTorch/torchvision/Transformers cũ hoặc API đã thay đổi | AIW-04 compatibility spike; pin môi trường đã kiểm chứng, lưu lock và không xử lý đủ 7 video trước khi smoke pass. |
| Colab mất phiên/không cấp T4 trong lúc demo | Notebook disconnect, GPU khác hoặc hết quota | Dùng Colab cho batch trước buổi bảo vệ; checkpoint theo video, xuất bundle, demo chính dùng dữ liệu đã index local. |
| Result bundle bị thiếu hoặc trộn lineage | Import sai model/config, thiếu frame/vector | Manifest/checksum/schema version; importer idempotent đi qua AIW-18, từ chối bundle không đầy đủ. |
| Ảnh→ảnh không đạt chất lượng | Query cùng người xếp hạng thấp | AIW-14, AIW-26; đo thực nghiệm và báo giới hạn. |
| Sampling làm đứt track | Track count tăng bất thường ở N=20 | AIW-08, AIW-11, AIW-27. |
| Admin chọn sampling tùy ý làm giảm chất lượng | N khác benchmark, số track đứt/bỏ sót tăng | Chỉ dùng default/preset allowlist; job snapshot N; AIW-08, AIW-19, AIW-27. |
| Representative frame xấu | Crop mờ, cắt người, embedding khó tìm | Top-3 bounded best-shot, hard filter, quality breakdown và fixture regression trong AIW-12/AIW-26. |
| RTSP không ổn định | Timeout/reconnect liên tục | AIW-09, AIW-20, AIW-28; demo chính vẫn dùng file. |
| Trộn encoder version | Search sai hoặc vector dimension mismatch | AIW-03, AIW-13, AIW-18. |
| Worker crash để lại dữ liệu dở dang | Track `PENDING`, object/vector thiếu | AIW-18, AIW-20. |
| Fake adapter lọt production | Kết quả có bbox/vector synthetic | AIW-03, AIW-05, AIW-24, AIW-29. |
| Lộ credential/dữ liệu hình ảnh | URL/frame/query xuất hiện trong log | AIW-09, AIW-23. |
| Không đủ dung lượng cho 7 video | Disk tăng nhanh | AIW-01, AIW-04, AIW-27; chỉ lưu frame đại diện. |
| Dataset 10,84 GiB bị commit nhầm | Thư mục bị force-add hoặc rule ignore bị xóa | `wildtrack-dataset/` đã nằm trong `.gitignore`; AIW-01 tiếp tục khóa local/LFS/download policy và kiểm tra staged files. |
| License Detector không phù hợp phạm vi phát hành | Dùng Ultralytics trong dự án không đáp ứng AGPL/giấy phép thương mại | AIW-03 ghi license/provenance; dùng YOLOX + ByteTrack làm đường dự phòng nếu cần. |
| Chưa có ngưỡng chất lượng chính thức | Không thể kết luận pass/fail AI | AIW-26 tạo baseline và trình người thực hiện duyệt ngưỡng. |

## 14. Thứ tự triển khai đề xuất

Ưu tiên hoàn thành lát cắt file-video trước:

1. AIW-00 → AIW-05: baseline, contract, registry, runtime và test doubles.
2. AIW-06 → AIW-08: nguồn file và sampling đúng timeline.
3. AIW-10 → AIW-14: Detector, Tracker, selector và RaSa Image Encoder thật.
4. AIW-16 → AIW-18: pipeline, worker loop và publication ba kho.
5. AIW-15 + AIW-25: query inference thật và E2E nghiệp vụ.
6. AIW-19 → AIW-24: vận hành, recovery, trạng thái, diagnostics và hardening.
7. AIW-26 → AIW-27: chất lượng 7 video và benchmark sampling.
8. AIW-09 + AIW-28: RTSP giả lập và bằng chứng tại nhà.
9. AIW-29: đóng gói và nghiệm thu.

RTSP có thể được phát triển sau khi đường file hoàn chỉnh vì đây không phải điều kiện bắt buộc của buổi demo, nhưng interface nguồn frame AIW-06 phải được thiết kế từ đầu để không khóa pipeline vào file video.

## 15. Tài liệu kỹ thuật tham khảo cho các quyết định bổ sung

Các nguồn dưới đây dùng để tham khảo cách hệ thống video analytics xử lý trade-off; chúng không thay thế ba tài liệu yêu cầu chính thức:

- [NVIDIA DeepStream Tracker](https://docs.nvidia.com/metropolis/deepstream/9.0/text/DS_plugin_gst-nvtracker.html): model/tracker được lựa chọn qua implementation và config đã biết; mô tả detector interval, tracker input, past-frame data và terminated track.
- [NVIDIA DeepStream Accuracy Tuning](https://docs.nvidia.com/metropolis/deepstream/7.1/text/DS_Accuracy.html): detection interval là trade-off kỹ thuật phụ thuộc tracker và phải được tune bằng số đo.
- [Azure AI Video Indexer — Featured clothing](https://learn.microsoft.com/en-us/azure/azure-video-indexer/observed-people-featured-clothing): xếp hạng candidate frame và lưu best frame cùng timestamp/bounding box; blur và overlap làm giảm chất lượng.
- [TrADe Re-ID](https://arxiv.org/abs/2209.06452): gom detection thành tracklet và chọn một ảnh chất lượng tốt đại diện thay vì đưa mọi crop vào gallery.
- [Google Colab FAQ](https://research.google.com/colaboratory/faq.html): tài nguyên/GPU và giới hạn phiên thay đổi động; VM có vòng đời tối đa và có thể bị ngắt.
- [Google Colab Runtime Versions](https://research.google.com/colaboratory/runtime-version-faq.html): runtime được cập nhật thường xuyên; notebook cần pin dependency riêng nếu cần tái lập.
- [NVIDIA T4 Datasheet](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-t4/t4-tensor-core-datasheet-951643.pdf): T4 có 16 GB GDDR6 và hỗ trợ CUDA/TensorRT/ONNX cho workload inference.
- [Ultralytics Tracking](https://docs.ultralytics.com/modes/track/): ByteTrack là baseline đơn giản/ít overhead cho camera tĩnh; tracker có thể thay bằng config, BoT-SORT hỗ trợ CMC/ReID khi cần.
- [Ultralytics License](https://www.ultralytics.com/license): code/model Ultralytics dùng AGPL-3.0 hoặc license thương mại tùy phạm vi sử dụng.
- [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) và [ByteTrack](https://github.com/FoundationVision/ByteTrack): đường detector/tracker tách rời, có model nhẹ và license Apache-2.0/MIT.
- [RaSa official repository](https://github.com/Flame-Chasers/RaSa): dependency upstream cũ cần compatibility spike trước khi chọn Colab runtime.
