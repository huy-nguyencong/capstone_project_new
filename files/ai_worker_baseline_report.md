# AIW-00 — Baseline AI Worker và ma trận truy vết

> Ngày thực hiện: 2026-09-25  
> Trạng thái: `DONE`
> Phạm vi: inventory và phân loại hiện trạng; chưa tích hợp Detector, Tracker hoặc RaSa production.

## 1. Nguồn đối chiếu

- `project_requirements.md`, trọng tâm mục 5 — luồng xử lý AI và tìm kiếm.
- `usecase_detail.md`, trọng tâm UC-04 đến UC-09.
- `architect.md`, trọng tâm worker tách tiến trình, file/RTSP, sampling, track buffer, RaSa và ba kho dữ liệu.
- `backend_implementation_plan.md`, trọng tâm BE-07 đến BE-15 và BE-20 đến BE-25.
- `ai_worker_implementation_plan.md`, quyết định đã khóa và AIW-00 đến AIW-29.

## 2. Kết luận baseline

Backend đã có nền tảng tốt cho upload video, processing job tuần tự, lease/cancel/retry, lưu một full frame+bbox+vector và chỉ công bố track khi đạt `READY`. Tuy nhiên, hệ thống **chưa có AI production**. Đường worker hiện tại chỉ chạy khi truyền `--demo`; Detector, Tracker và Encoder đều là deterministic fake.

Các kết luận quan trọng:

1. `person-search-worker` không có `--demo` fail-closed. Đây là guard tốt, không có silent fallback từ production sang fake trong worker CLI.
2. Demo data dùng collection alias `person_track_embeddings_demo`, tách khỏi alias production.
3. Model registry, pipeline interface và HTTP encoder gateway mới là scaffolding; chưa kiểm tra artifact Detector/Tracker, chưa có model preflight và chưa có RaSa service thật.
4. Camera diagnostics hiện chỉ probe trạng thái RTSP rồi chạy model trên `synthetic_frame()`, không đọc frame thật từ camera. Vì vậy chưa đáp ứng UC-07 production.
5. `MonitoringService` mặc định dùng `Pipeline.demo`; `SearchService` tự chọn `DemoEncoderGateway` khi active config có version `fake_demo_v1`. Đây là đường demo có chủ đích nhưng chưa bị cấm theo environment production.
6. API upload hiện nhận raw `sampling_interval` từ Admin trong khoảng `1..1000`, trái với quyết định mới rằng Admin không được nhập raw `N`.
7. Representative frame hiện do `DemoTracker` chọn frame đầu; chưa có bounded top-3 best-shot selector.
8. Chưa có RTSP frame source, Detector/Tracker production, RaSa Image/Text Encoder production, result bundle Colab, worker heartbeat độc lập hoặc metrics stage thật.

## 3. Phân loại sử dụng trong báo cáo

| Nhãn | Ý nghĩa |
| --- | --- |
| `PRODUCTION_CORE` | Logic thật, có invariant rõ và test tương xứng; có thể tái sử dụng cho AI production. |
| `PARTIAL` | Có logic thật nhưng contract/cấu hình/vận hành chưa đủ theo kế hoạch AI worker. |
| `SCAFFOLDING` | Khung tích hợp hoặc interface đã có, chưa có implementation production hoàn chỉnh. |
| `DEMO_FAKE` | Chỉ sinh dữ liệu deterministic để kiểm thử luồng; không phải AI thật. |
| `MISSING` | Chưa có module hoặc đường chạy. |

## 4. Sơ đồ module hiện tại

```text
Admin upload API
      |
      v
JobService --> VideoStaging --> PostgreSQL ProcessingJob
      |
      v
person-search-worker --demo
      |
      v
VideoWorker --> VideoFrameSource --> Pipeline.demo
                                    |-> DemoDetector
                                    |-> DemoTracker
                                    `-> DemoEncoder
                                             |
                                             v
                                  TrackIngestionService
                                  /        |         \
                           PostgreSQL    MinIO     Milvus demo alias

Search API --> SearchService --> DemoEncoderGateway hoặc HttpEncoderGateway
                              --> Milvus search --> READY track metadata

Camera diagnostic --> RTSP availability probe
                  --> synthetic_frame()
                  --> Pipeline.demo mặc định
```

Kiến trúc chưa có:

```text
RTSP/File FrameSource contract hoàn chỉnh
       -> production DetectorAdapter
       -> production TrackerAdapter
       -> bounded track buffer + best-shot selector
       -> RaSa Image Encoder
       -> production TrackPublisher / BundlePublisher
```

## 5. Inventory và phân loại toàn bộ thành phần AI liên quan

| Thành phần | File hiện tại | Phân loại | Bằng chứng hiện có | Gap chính / task kế tiếp |
| --- | --- | --- | --- | --- |
| Worker CLI/supervisor | `backend/src/person_search/workers/main.py` | `PARTIAL` | Tiến trình riêng, `--once`, child timeout, signal stop; từ chối chạy khi thiếu `--demo`. | Chưa có production pipeline factory, registry/preflight thật. AIW-03, AIW-04, AIW-16, AIW-17. |
| Worker orchestration | `backend/src/person_search/workers/runner.py` | `PARTIAL` | Global advisory lock, claim/checkpoint, stage error code, EOF finish, cleanup. | Contract còn gắn chặt pipeline cũ; chưa có taxonomy lỗi chuẩn, stage metrics, production adapters. AIW-02, AIW-16, AIW-17, AIW-20, AIW-21. |
| File decoder | `backend/src/person_search/workers/pipeline.py::VideoFrameSource` | `PARTIAL` | PyAV đọc file private, timestamp từ PTS, giới hạn 4K, sampling trước AI. | `SourceFrame` thiếu camera/size contract; lifecycle chưa có `open/read/flush/close`; chưa có corruption policy. AIW-06 đến AIW-08. |
| Pipeline protocols | `backend/src/person_search/workers/pipeline.py` | `SCAFFOLDING` | Có `FrameSource`, `Detector`, `Tracker`, `Encoder`, `CompletedTrack`. | Detection chỉ là bbox, thiếu class/confidence/model lineage; không có selector/publisher contract; typing/lifecycle chưa chặt. AIW-02. |
| Detector | `DemoDetector` | `DEMO_FAKE` | Luôn sinh một bbox giữa ảnh. | Không phát hiện người thật. AIW-10. |
| Tracker | `DemoTracker` | `DEMO_FAKE` | Một track mỗi 5 sampled frames, deterministic. | Không association thật; chọn frame đầu; chưa có lost/confirmed policy production. AIW-11, AIW-12. |
| Image encoder trong worker | `DemoEncoder` | `DEMO_FAKE` | Hash crop thành vector 256 chiều chuẩn hóa. | Không phải RaSa, không có preprocessing/checkpoint thật. AIW-13, AIW-14. |
| Representative frame | `DemoTracker.first` và `Pipeline.request()` | `DEMO_FAKE` | Lưu một full frame+bbox; crop chỉ được tạo tạm trong hàm request. | Chưa có top-3 buffer, quality filter/ranking, memory bound. AIW-12. |
| Processing job API/service | `api/v1/jobs.py`, `services/jobs.py`, model `processing_job.py` | `PARTIAL` | Idempotent upload, sequential claim, lease, cancel, progress, cleanup, sanitized error. | Cho phép raw sampling `1..1000`; chưa có job/bundle mode Colab; heartbeat chỉ tồn tại khi có job. AIW-08, AIW-17, AIW-19, AIW-21. |
| Video staging | `services/video_staging.py` | `PRODUCTION_CORE` | Private generated filename, size/disk limits, signature, ffprobe và decode smoke, cleanup. | Cần reuse/adapter hóa cho dataset và Colab import; máy hiện tại thiếu FFmpeg. AIW-01, AIW-07, AIW-29. |
| Model registry/config | `services/cameras.py`, `config/models.demo.json`, model `ai_config.py` | `PARTIAL` | Allowlist ID, compatibility list, versioned active config, optimistic concurrency. | `available` được tin từ JSON; thiếu adapter kind, artifact/checksum Detector/Tracker, license/device/preflight. `apply_config` mặc định là no-op trong app wiring. AIW-03, AIW-04, AIW-19. |
| Track ingestion/publisher | `services/track_ingestion.py` | `PRODUCTION_CORE` | Register `PENDING`, upload/verify frame, upsert/verify vector, publish `READY`, retry/outbox/idempotency. | Cần adapter `TrackPublisher` rõ và `BundlePublisher`/importer; kết nối với pipeline production. AIW-18, AIW-20. |
| Durable track schema | `storage/contracts.py`, model `person_track.py` | `PRODUCTION_CORE` | Timeline, bbox bounds, complete JPEG, finite normalized vector, one object key và state transition. | Chưa lưu đầy đủ detector/tracker/sampling lineage trực tiếp trên track; cần review cùng contract AIW-02/18. |
| MinIO frame store | `storage/minio/frames.py` | `PRODUCTION_CORE` | Put/head/delete frame và object metadata đã có test. | Giữ nguyên qua publisher abstraction. AIW-18. |
| Milvus vector index | `storage/milvus/vectors.py` | `PRODUCTION_CORE` | Versioned collection, alias, upsert/get/search đã có test. | Chưa có RaSa vector thật; cần encoder dimension/version preflight. AIW-13 đến AIW-15, AIW-18. |
| Query encoder gateway | `services/searches.py` | `PARTIAL` | Image/text HTTP gateway có timeout/version/dimension/norm validation. | Chưa có RaSa service; demo gateway tự bật theo active version; text tự do chưa enforce tiếng Anh. AIW-13, AIW-15. |
| Attribute prompt | `services/searches.py::attributes_prompt` | `PRODUCTION_CORE` | Allowlist thuộc tính và prompt deterministic bằng tiếng Anh. | Mở rộng schema chỉ sau khi benchmark/requirement thay đổi. AIW-15. |
| Vector search/read path | `services/track_search.py`, `services/searches.py` | `PRODUCTION_CORE` | Authorization theo area/camera, chỉ READY, filter/ranking, score trả trong response. | Cần chứng minh bằng embedding RaSa thật. AIW-15, AIW-25, AIW-26. |
| Camera runtime probe | `services/camera_runtime.py` | `PRODUCTION_CORE` cho connectivity | RTSP credential encryption, network allowlist, ffprobe timeout. | Đây không phải RTSP frame source. AIW-09. |
| Camera pipeline diagnostic | `services/monitoring.py::run_pipeline_steps` | `DEMO_FAKE`/`PARTIAL` | Có outcome theo stage và xử lý `INCONCLUSIVE`. | Sau RTSP probe vẫn dùng synthetic frame; default `Pipeline.demo`; chưa xác minh model production trên frame thật. AIW-22. |
| Search component diagnostic | `services/monitoring.py` | `PARTIAL` | Gọi image/text gateway, kiểm dimension/norm và storage health. | Demo encoder được coi `UP` mà không inference trong `_encoder_status`; cần production fixture/model preflight. AIW-22. |
| Worker/system status | `services/monitoring.py` | `PARTIAL` | Suy diễn queue/running/error từ job và lease. | Không có idle worker heartbeat; `source_fps`, `processed_fps`, `latency_ms` luôn `None`. AIW-21. |
| Audit/redaction | `services/audit.py` | `PRODUCTION_CORE` | Có event job/config và redact embedding/frame/RTSP fields. | Cần correlation xuyên pipeline và taxonomy AI. AIW-23. |
| RTSP FrameSource | Không có | `MISSING` | Chỉ có connectivity probe. | AIW-06, AIW-09, AIW-28. |
| RaSa runtime/Image/Text Encoder | Không có | `MISSING` | Chỉ có constants và HTTP gateway contract. | AIW-04, AIW-13 đến AIW-15. |
| Best-shot selector/bounded buffer | Không có | `MISSING` | Demo giữ frame đầu. | AIW-12. |
| Colab result bundle/importer | Không có | `MISSING` | Chưa có schema/export/import. | AIW-18, AIW-26, AIW-29. |
| Quality evaluation/benchmark | Không có | `MISSING` | Chưa có dataset manifest/report script. | AIW-01, AIW-26, AIW-27. |

## 6. Các đường có thể dùng demo/fake

| Đường chạy | Điều kiện kích hoạt | Mức cô lập hiện tại | Đánh giá |
| --- | --- | --- | --- |
| Worker demo | CLI bắt buộc truyền `--demo`; config phải khớp toàn bộ demo IDs/checksum. | Tốt; không có fallback im lặng. | Giữ cho test, chuyển namespace fake sang test-support ở AIW-05. |
| Demo model registry | `PERSON_SEARCH_MODEL_REGISTRY` trỏ tới `config/models.demo.json`, sau đó Admin activate cặp demo. | Có nhãn demo nhưng không chặn `production` environment. | P0: registry production phải từ chối entry `DEMO_FAKE`. |
| Search demo | Active encoder version bằng `fake_demo_v1`. | Dùng Milvus alias riêng `person_track_embeddings_demo`. | P0: chỉ cho phép ở environment test/demo tường minh. |
| Camera diagnostic demo | `MonitoringService` không được inject factory khác nên mặc định `Pipeline.demo`. | Config khác demo sẽ fail thay vì fallback. | P0: diagnostics production phải dùng factory thật và frame thật. |
| Synthetic storage benchmark/tests | Tool/test gọi fake data trực tiếp. | Tách trong `backend/tools` và `backend/tests`; output có nhãn synthetic. | Chấp nhận nếu không được dùng làm bằng chứng AI quality. |

## 7. Ma trận requirement → module → test → bằng chứng

| ID | Requirement/Use case | Module hiện tại | Test/bằng chứng hiện tại | Mức đáp ứng | Task đóng gap |
| --- | --- | --- | --- | --- | --- |
| R-01 | Worker tách khỏi Flask, job tuần tự | `workers/main.py`, `runner.py`, `services/jobs.py` | `test_video_jobs.py`; advisory lock/lease tests | Một phần: orchestration thật, AI fake | AIW-16, AIW-17, AIW-20 |
| R-02 | File và RTSP dùng chung pipeline | `VideoFrameSource`; RTSP chỉ có `CameraRuntime.probe` | Unit camera runtime; chưa có source contract test | Thiếu RTSP source và common lifecycle | AIW-06, AIW-07, AIW-09, AIW-28 |
| R-03 | Sampling trước Detector/Tracker, giữ source timeline | `VideoFrameSource.frames`, `VideoWorker.process` | Integration N=10/N=20 và timestamp | Một phần; raw `N` vẫn từ Admin | AIW-08, AIW-19, AIW-27 |
| R-04 | Detector → Tracker → representative frame → RaSa | `Pipeline` protocols + demo adapters | Demo integration/smoke | Chỉ fake | AIW-02, AIW-10 đến AIW-16 |
| R-05 | Registry Detector/Tracker allowlist, kiểm tương thích | `CameraService` | `test_camera_admin.py` | Một phần; thiếu artifact/preflight/license | AIW-03, AIW-04, AIW-19 |
| R-06 | Bật/tắt AI theo camera | `CameraService`, `JobService.eligible/checkpoint/finish` | Camera admin và video job tests | Core có sẵn | AIW-17, AIW-19 |
| R-07 | Một track lưu một full frame+bbox, crop tạm | `TrackIngestionRequest`, `PersonTrack`, `Pipeline.request` | Storage contract/ingestion tests | Storage đạt; selector chưa đạt | AIW-12, AIW-18 |
| R-08 | Track `READY` chỉ khi ba kho nhất quán | `TrackIngestionService` | Unit/integration/e2e storage workflow | Đạt ở storage layer | AIW-18, AIW-20 |
| R-09 | RaSa cùng checkpoint cho stored/query embedding | Constants + `HttpEncoderGateway` | Gateway validation tests | Chưa có RaSa runtime | AIW-13 đến AIW-15 |
| R-10 | Text/attribute chỉ tiếng Anh | `attributes_prompt`, `search_text` | Prompt tests | Attribute đạt; free text chưa enforce | AIW-15 |
| R-11 | Matching Score chỉ tồn tại trong search | Search response + Case schema/service | Search/Case unit và integration tests | Đạt ở backend hiện tại | AIW-25 |
| R-12 | Track là appearance per camera/job, không global merge | Deterministic ID từ job+track key | Crash replay/idempotency test | Nền tảng phù hợp; tracker thật chưa có | AIW-11, AIW-17 |
| R-13 | EOF/cancel theo policy đã khóa | `VideoWorker.process`, `tracker.finish/close` | Integration EOF/cancel/crash tests | Một phần; chỉ demo tracker | AIW-11, AIW-16, AIW-17 |
| R-14 | Status, heartbeat, metrics thật | `MonitoringService` | Monitoring unit/API tests | Status suy diễn; thiếu idle heartbeat/metrics | AIW-21 |
| R-15 | Diagnostics dùng nguồn và model thật | `run_pipeline_steps`, encoder gateway | Monitoring unit tests | Không đạt: synthetic frame/demo default | AIW-22 |
| R-16 | Retry/idempotency/recovery | `JobService`, `VideoWorker`, `TrackIngestionService` | Worker crash/replay và ingestion failure tests | Core tốt, cần chuẩn hóa AI errors | AIW-20, AIW-24 |
| R-17 | Colab batch không là online dependency | Không có | Chưa có | Thiếu bundle/export/import | AIW-18, AIW-26, AIW-29 |
| R-18 | Đánh giá 7 video và benchmark N | Không có | Dataset mới chỉ được cung cấp | Thiếu manifest/evaluation scripts | AIW-01, AIW-26, AIW-27 |

## 8. Danh sách gap theo ưu tiên

### P0 — Chặn AI production hoặc có thể gây hiểu nhầm

| Gap | Tác động | Xử lý |
| --- | --- | --- |
| Không có Detector/Tracker/RaSa production | Ứng dụng chỉ tạo kết quả giả lập | AIW-03, AIW-04, AIW-10, AIW-11, AIW-13 đến AIW-16 |
| Demo registry/gateway chưa bị chặn theo environment | Có thể activate demo trên deployment được gọi là production | AIW-03, AIW-05, AIW-19 |
| `CameraService.apply_config` là no-op trong app wiring | API có thể báo cấu hình đã áp dụng dù worker chưa nạp được model | AIW-03, AIW-04, AIW-19 |
| Diagnostics dùng synthetic frame sau RTSP probe | Có thể báo model thành công mà chưa xử lý frame camera thật | AIW-09, AIW-22 |
| API nhận raw `sampling_interval` 1–1000 | Trái quyết định sampling allowlist, có thể phá chất lượng track | AIW-08, AIW-19 |
| Chưa có RaSa compatibility/preflight | Không biết checkpoint/runtime có chạy trên local hoặc Colab T4 | AIW-04, AIW-13 |

### P1 — Cần cho lát cắt end-to-end đúng kiến trúc

| Gap | Tác động | Xử lý |
| --- | --- | --- |
| Contract AI còn thiếu metadata/lifecycle/error model | Adapter framework dễ rò vào orchestration, khó thay model | AIW-02 |
| Không có best-shot buffer/selector | Representative frame hiện là frame đầu, chất lượng embedding thấp | AIW-12 |
| Không có RTSP frame source | Chưa chứng minh file/RTSP dùng chung pipeline | AIW-06, AIW-09, AIW-28 |
| Không có worker heartbeat độc lập và stage metrics | Admin không phân biệt idle worker sống với worker chết | AIW-21 |
| Không có Colab result bundle/importer | Batch GPU chưa nối an toàn với local system of record | AIW-18, AIW-29 |
| Worker tests chính phụ thuộc PostgreSQL disposable + FFmpeg | Feedback loop cho orchestration chậm/khó chạy ở máy mới | AIW-05, AIW-24; smoke in-memory đã bổ sung trong AIW-00 |

### P2 — Đo lường và hardening trước demo

- Dataset manifest, query set và ground-truth evaluation: AIW-01, AIW-26.
- Benchmark local/Colab, sampling `N=10`/`N=20`: AIW-27.
- Failure injection, log/correlation/redaction hoàn chỉnh: AIW-23, AIW-24.
- RTSP evidence và runbook bảo vệ: AIW-28, AIW-29.

## 9. File/module đích cho các task tiếp theo

| Task | Module đích dự kiến |
| --- | --- |
| AIW-01 | `backend/tools/wildtrack_manifest.py`, manifest/report dưới `files/` hoặc `docs/`; không commit dataset binary. |
| AIW-02 | Tách `workers/contracts.py`, `workers/errors.py`; migrate contract AI khỏi `pipeline.py` nhưng tái sử dụng `storage/contracts.py`. |
| AIW-03 | Tạo `ai/registry.py` và manifest production; tích hợp `services/cameras.py`. |
| AIW-04 | Tạo `ai/preflight.py`, CLI/report preflight local/Colab. |
| AIW-05 | `tests/ai_fakes/` hoặc `tests/support/ai.py`; khóa demo adapters khỏi production wiring. |
| AIW-06 đến AIW-09 | `workers/sources/base.py`, `file.py`, `sampling.py`, `rtsp.py`; thay `VideoFrameSource` cũ có migration test. |
| AIW-10 | `ai/detectors/` với adapter YOLO đầu tiên và contract tests. |
| AIW-11 | `ai/trackers/bytetrack.py`, sau đó `botsort.py`; lifecycle/timeout tests. |
| AIW-12 | `ai/tracks/buffer.py`, `selector.py`; fixture quality tests. |
| AIW-13 đến AIW-15 | `ai/encoders/rasa/`, encoder service/entrypoint; cập nhật `services/searches.py`. |
| AIW-16 | Refactor `workers/pipeline.py` thành factory/orchestrator production. |
| AIW-17 | Hoàn thiện `workers/runner.py`, `services/jobs.py` theo contract mới. |
| AIW-18 | `workers/publishers/track.py`, `bundle.py`, local importer; reuse `TrackIngestionService`. |
| AIW-19 | Config apply coordinator giữa `services/cameras.py`, registry và worker. |
| AIW-20 | `workers/recovery.py` và mở rộng job/ingestion reconciliation. |
| AIW-21 | `workers/metrics.py`, worker heartbeat model/repository và `MonitoringService`. |
| AIW-22 | `services/diagnostics.py`; thay synthetic production path trong `monitoring.py`. |
| AIW-23 | Logging context/redaction/correlation xuyên API → job → worker → storage. |
| AIW-24 | Unit/contract/integration/failure tests trong `backend/tests/ai_worker/`. |
| AIW-25 | E2E thật trong `backend/tests/e2e/`; không seed track để bỏ qua worker. |
| AIW-26, AIW-27 | `backend/tools/ai_quality.py`, `ai_benchmark.py` và report versioned. |
| AIW-28 | MediaMTX/FFmpeg fixture config và RTSP evidence script dưới `infra/`/`backend/tools/`. |
| AIW-29 | Notebook/lock Colab, deployment config và runbook dưới `docs/`/`files/`. |

Tên module có thể điều chỉnh trong lúc thực hiện AIW-02 để khớp package boundary, nhưng trách nhiệm và nơi tích hợp đã xác định.

## 10. Bằng chứng kiểm thử AIW-00

| Lệnh | Kết quả |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -m unit` | Lần chạy cuối: `324 passed, 25 deselected`. |
| `backend/.venv/Scripts/python.exe -m pytest tests/unit/test_worker_demo_smoke.py -q` | `1 passed`; worker demo chạy hoàn toàn in-memory, tạo một `TrackIngestionRequest`, không mở storage production. |
| `backend/.venv/Scripts/python.exe -m ruff check .` | `All checks passed`. |
| `backend/.venv/Scripts/python.exe -m compileall -q src tests/unit/test_worker_demo_smoke.py` | Thành công. |

Existing full worker integration coverage nằm ở `backend/tests/integration/test_video_jobs.py`, gồm video decode, N=10/N=20, cancel, crash replay, advisory lock và sanitized error. Không chạy lại nhóm này trong AIW-00 vì máy hiện tại không có `PERSON_SEARCH_CAMERA_TEST_DSN` và không tìm thấy `ffmpeg`; đây không phải blocker cho smoke in-memory nhưng là prerequisite của AIW-01/AIW-07/AIW-24.

## 11. Đánh giá tiêu chí hoàn thành

- [x] Inventory worker entrypoint, pipeline, adapter, job service, ingestion và diagnostics.
- [x] Phân loại `PRODUCTION_CORE`, `PARTIAL`, `SCAFFOLDING`, `DEMO_FAKE`, `MISSING` cho toàn bộ thành phần AI hiện hữu.
- [x] Xác định các đường demo/fake và mức cô lập.
- [x] Lập ma trận requirement → module → test → bằng chứng → task đóng gap.
- [x] Có sơ đồ module hiện tại và danh sách gap theo ưu tiên.
- [x] Có module đích dự kiến cho từng task tiếp theo.
- [x] Unit baseline đạt.
- [x] Smoke worker demo không ghi storage production đạt.
- [x] Review và chấp thuận để chuyển AIW-00 từ `REVIEW` sang `DONE`.

AIW-00 không triển khai AI production và không tự động bắt đầu AIW-01/AIW-02 trước khi được review.
