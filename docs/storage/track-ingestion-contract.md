# Track ingestion contract v1

Hợp đồng này là biên giữa AI worker và storage service. Bản executable nằm tại
`person_search.storage.contracts`.

## Producer và consumer

- **Producer:** AI worker sau khi một track kết thúc và đã chọn representative frame.
- **Consumer:** storage ingestion service được hiện thực ở STO-11.
- **Delivery:** at-least-once. Producer phải retry bằng cùng `track_id`.

## Request

| Field | Kiểu | Quy tắc |
| --- | --- | --- |
| `track_id` | UUIDv4 | Khóa idempotency và ID xuyên ba kho. |
| `camera_id` | UUIDv4 | Camera logic đã tồn tại. |
| `area_id` | UUIDv4 | Snapshot từ Camera; consumer đối chiếu PostgreSQL. |
| `processing_job_id` | UUIDv4 | Job file/RTSP sinh track. |
| `ai_config_version_id` | UUIDv4 | Phiên bản Detector/Tracker đã dùng. |
| `timeline_origin_utc` | UTC datetime | Mốc tuyệt đối của timeline nguồn. |
| `source_frame_index` | integer | Frame đại diện, `>= 0`. |
| `source_started_at_ms` | integer | Offset bắt đầu track, `>= 0`. |
| `representative_frame_timestamp_ms` | integer | Nằm trong khoảng start/end. |
| `source_ended_at_ms` | integer | `>= source_started_at_ms`. |
| `bbox` | `BoundingBoxPixels` | Pixel nguyên trên full frame gốc. |
| `frame_bytes` | bytes | JPEG đầy đủ, không rỗng. |
| `frame_media_type` | string | Cố định `image/jpeg` trong v1. |
| `embedding` | sequence float | 256 số hữu hạn, L2-normalized. |
| `encoder` | `EncoderManifest` | `rasa_cuhk_pedes_v1`, dimension 256, metric IP, checkpoint SHA-256. |

`appeared_at_utc` không do worker nhập riêng; contract tính từ
`timeline_origin_utc + source_started_at_ms` để tránh hai nguồn thời gian mâu thuẫn.

## Invariant phía consumer

1. Đối chiếu Camera tồn tại và `Camera.area_id == request.area_id`.
2. Đối chiếu job thuộc camera và AI config version tồn tại.
3. Tính SHA-256 trên `frame_bytes`; không tin checksum do producer gửi.
4. Kiểm tra vector đúng dimension, finite, L2 norm và encoder version.
5. Sinh object key bằng hàm deterministic; không nhận object key từ producer.
6. Track chỉ searchable khi Milvus `published=true` và PostgreSQL `READY`.
7. Không lưu Matching Score, person crop hoặc confidence Detector trong contract nghiệp vụ.

## Kết quả idempotency

| Tình huống | Kết quả |
| --- | --- |
| `track_id` mới | Bắt đầu write flow với `PENDING`. |
| Retry cùng ID và cùng payload identity | Tiếp tục bước chưa hoàn tất hoặc trả trạng thái hiện có. |
| Cùng ID nhưng camera/job/frame checksum/encoder khác | Conflict; không ghi đè dữ liệu cũ. |
| Lỗi transient MinIO/Milvus | Ghi lỗi/retry metadata; không publish. |
| Lỗi validation | Từ chối, không tạo artifact ngoài. |
| Retry vượt giới hạn | Chuyển `FAILED`; reconciliation/manual retry có thể đưa về `PENDING`. |

## Ví dụ rút gọn

```python
TrackIngestionRequest(
    track_id=UUID("..."),
    camera_id=UUID("..."),
    area_id=UUID("..."),
    processing_job_id=UUID("..."),
    ai_config_version_id=UUID("..."),
    timeline_origin_utc=datetime(..., tzinfo=timezone.utc),
    source_frame_index=300,
    source_started_at_ms=10_000,
    representative_frame_timestamp_ms=11_000,
    source_ended_at_ms=12_000,
    bbox=BoundingBoxPixels(x=100, y=40, width=80, height=210,
                           frame_width=1920, frame_height=1080),
    frame_bytes=b"...jpeg...",
    frame_media_type="image/jpeg",
    embedding=(...),
    encoder=EncoderManifest(...),
)
```

## Versioning

- Thay đổi backward-compatible thêm field optional cần tăng minor contract version trong tài
  liệu và test.
- Thay bbox semantics, ID format, vector dimension, encoder checkpoint hoặc write invariant là
  breaking change; cần ADR và contract version mới.
