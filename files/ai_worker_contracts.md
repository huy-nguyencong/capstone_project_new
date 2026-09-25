# AI worker contracts và error taxonomy

> Task: AIW-02  
> Trạng thái: `REVIEW` sau khi code và contract tests đạt

## 1. Ranh giới contract

Contract chuẩn nằm tại `backend/src/person_search/workers/contracts.py` và không phụ thuộc API của YOLO, ByteTrack, BoT-SORT hay RaSa. Adapter production và fake test phải chuyển dữ liệu framework-specific sang các type này ngay tại boundary.

Các invariant chính:

- `SourceFrame` luôn mang camera, source frame index, source timestamp, ảnh giải mã và kích thước khớp ảnh.
- `SampledFrame` ghi rõ interval và sample sequence; sampling diễn ra trước Detector/Tracker.
- `Detection` chỉ cho lớp chuẩn hóa `person`, confidence hữu hạn trong `[0, 1]` và bbox hợp lệ trong full frame.
- `TrackUpdate` dùng local track ID theo camera; không phải danh tính con người và không dùng để merge xuyên camera.
- `RepresentativeCandidate` giữ full frame+bbox và quality nội bộ. Person crop chỉ được tạo tạm lúc encode.
- `CompletedTrack` khóa camera/job/config, timeline nguồn, representative candidate, sampling và lineage Detector/Tracker/Encoder.
- `EmbeddingVector` khóa dimension, tính hữu hạn và chính sách L2 normalization.
- `PublishedTrack` chỉ được tạo ở trạng thái `READY`, với cùng một track identity ở metadata và vector index.
- `ResultBundleManifest` chỉ nhận relative path an toàn và SHA-256 hợp lệ.
- Projection dùng cho diagnostics loại bỏ image bytes và vector values.

`BoundingBoxPixels` và storage invariant hiện hữu tiếp tục được tái sử dụng từ `person_search.storage.contracts`; không tạo định dạng bbox thứ hai.

## 2. Lifecycle chuẩn

```text
FrameSource.open(source, camera)
  └─ read() -> SourceFrame | EOF
       └─ sampler -> SampledFrame
            └─ Detector.open/detect/close
                 └─ Tracker.open/update/flush/close
                      └─ TrackSelector.open/consider/flush/close
                           └─ temporary person crop
                                └─ ImageEncoder.open/encode/close
                                     └─ TrackPublisher.open/publish/flush/close
```

- `flush()` chỉ xuất phần state còn lại; không tự mở lại component.
- `close()` phải idempotent. `IdempotentCloseMixin` bảo đảm resource-release chỉ chạy một lần, kể cả lần release đầu phát sinh lỗi.
- `FrameSource.read()` trả `None` tại EOF.
- Adapter không được fallback từ production sang fake khi `open()` thất bại.
- Orchestrator phải đóng component theo thứ tự ngược với lúc mở.

Pipeline demo cũ đã dùng `SourceFrame` và `Detection` chuẩn hóa, nhưng vẫn là fake cô lập. Việc chuyển hoàn toàn worker orchestration sang lifecycle mới thuộc AIW-06/AIW-16; contract đã khóa để các adapter đó có thể thay thế độc lập.

## 3. Sequence dữ liệu production

```text
source frame
  -> sampling decision (source timeline không đổi)
  -> person detections
  -> camera-local track updates
  -> bounded candidate buffer + representative selection
  -> one CompletedTrack
  -> transient bbox crop
  -> one EmbeddingVector
  -> publish full representative frame + bbox + vector + metadata
  -> PublishedTrack(READY)
```

Không lưu person crop. Detector confidence, quality components và total quality không đi vào Case DTO. Matching score chỉ tồn tại trong response tìm kiếm, không thuộc các contract track/Case.

## 4. Error taxonomy

`backend/src/person_search/workers/errors.py` khóa mười stage:

| Stage | Ví dụ code | Retry mặc định |
| --- | --- | --- |
| `SOURCE` | `source_open_failed`, `source_invalid_frame` | theo code |
| `SAMPLING` | `sampling_invalid_config`, `sampling_timeline_invalid` | không |
| `DETECTOR` | `detector_unavailable`, `detector_output_invalid` | theo code |
| `TRACKER` | `tracker_inference_failed`, `tracker_output_invalid` | theo code |
| `SELECTOR` | `selector_failed`, `selector_no_representative` | không |
| `IMAGE_ENCODER` | unavailable/inference/output invalid | theo code |
| `TEXT_ENCODER` | unavailable/inference/output invalid | theo code |
| `STORAGE` | unavailable/conflict/publish failed | theo code |
| `CANCELLATION` | `cancelled` | không |
| `RESOURCE` | `device_unavailable`, `resource_exhausted` | theo code |

Retryability là thuộc tính của error code, không được đoán chỉ từ Python exception type. `AIWorkerError.to_public_dict()` chỉ trả `code`, `stage`, `retryable` và public message cố định. Internal detail, exception gốc, URL/credential, local path, frame và embedding không được serialize ra API/job status/audit.

## 5. Quy tắc tích hợp task sau

1. AIW-03 registry cung cấp `ModelLineage` đã xác minh checksum.
2. AIW-06 đến AIW-15 implement đúng Protocol tương ứng, dùng `IdempotentCloseMixin` hoặc hành vi tương đương.
3. AIW-16 orchestration kiểm tra output contract sau mỗi boundary và map lỗi adapter sang `AIWorkerError`.
4. AIW-17/AIW-20 dùng `retryable` trong taxonomy để quyết định retry job; không tiếp tục dùng stage string tự do.
5. AIW-18 map `CompletedTrack` + `EmbeddingVector` sang storage contract và chỉ trả `PublishedTrack` sau khi ba kho nhất quán.
