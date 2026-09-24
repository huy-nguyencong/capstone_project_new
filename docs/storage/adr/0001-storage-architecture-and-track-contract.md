# ADR-0001: Kiến trúc lưu trữ và hợp đồng PersonTrack

- **Trạng thái:** Accepted
- **Ngày:** 2026-09-25
- **Phạm vi:** PostgreSQL, Milvus, MinIO và đường ghi `PersonTrack`
- **Thay thế:** các đề xuất chưa chốt trước đây nếu mâu thuẫn với ADR này

## Bối cảnh

Ứng dụng lưu một kết quả cho mỗi lần xuất hiện/track của người trên một camera. Một track
gồm metadata nghiệp vụ, full frame đại diện, bounding box và embedding RaSa. Dữ liệu này
phải hỗ trợ tìm kiếm theo vector, lọc theo khu vực/camera/thời gian và tiếp tục hiển thị
được khi User hoặc Camera không còn hoạt động.

Không có transaction phân tán nguyên tử giữa PostgreSQL, Milvus và MinIO. Vì vậy hệ thống
cần một nguồn sự thật, một state machine và write ordering idempotent để không trả track
dở dang.

## Quyết định

### 1. Trách nhiệm của từng kho

**PostgreSQL là nguồn sự thật nghiệp vụ và quyền truy cập.** PostgreSQL lưu User, Area,
Camera, cấu hình AI, processing job, PersonTrack, Case, CaseResult, audit log, trạng thái
ingestion và outbox/retry. Mọi quyết định quyền cuối cùng phải được kiểm tra bằng dữ liệu
PostgreSQL.

**Milvus là chỉ mục có thể tái tạo, không phải nguồn sự thật.** Milvus lưu một vector ảnh
cho mỗi track cùng scalar field dùng để lọc trước top-k: `track_id`, `area_id`, `camera_id`,
`appeared_at_epoch_ms`, `encoder_version` và `published`. Milvus không lưu Case/User và
không tự quyết định quyền.

**MinIO lưu object ảnh bất biến.** Ứng dụng lưu đúng một full frame JPEG đại diện cho mỗi
track. Person crop và ảnh full frame có bounding box được dựng động, không lưu thành object
độc lập. Bucket không public; backend kiểm tra quyền trước khi đọc ảnh.

### 2. Định danh

- Tất cả aggregate/entity ID do application tạo bằng **UUIDv4** trước khi ghi storage.
- PostgreSQL dùng kiểu `uuid`; API dùng chuỗi canonical lowercase có dấu gạch ngang.
- Milvus dùng `track_id` dạng `VARCHAR(36)` làm primary key.
- MinIO object key chứa UUID canonical; không dùng tên camera, filename upload hoặc dữ liệu
  do người dùng nhập làm path.
- `track_id` đồng thời là khóa idempotency của thao tác ingest. Cùng `track_id` và cùng nội
  dung là retry; cùng `track_id` nhưng checksum/vector metadata khác là conflict.

UUIDv4 được chọn vì có trong Python 3.11+, không cần dependency bổ sung và có thể tạo trước
mọi I/O. Tính thứ tự thời gian được xử lý bằng cột timestamp/index riêng, không dựa vào UUID.

### 3. Thời gian

- PostgreSQL lưu thời gian tuyệt đối bằng `timestamptz` và chuẩn hóa UTC.
- API/contract biểu diễn UTC bằng ISO 8601 kết thúc bằng `Z`.
- Timestamp dùng trong Milvus là Unix epoch milliseconds (`int64`).
- Mỗi processing job có `timeline_origin_utc`:
  - File video: thời điểm bắt đầu bản ghi phải được cung cấp hoặc lấy từ metadata đáng tin
    cậy; không âm thầm dùng thời điểm upload.
  - RTSP: mốc UTC của clock thu frame.
- Track lưu `source_started_at_ms`, `source_ended_at_ms` và
  `representative_frame_timestamp_ms`, đều là offset không âm trên timeline nguồn.
- `appeared_at_utc = timeline_origin_utc + source_started_at_ms`.
- `ingested_at_utc` do storage service tạo bằng server clock và không được dùng thay cho
  thời điểm xuất hiện.

Thiết kế này giữ đúng thời gian trong video ngay cả khi file được xử lý nhiều giờ/ngày sau.

### 4. Bounding box và frame

- Bounding box dùng pixel nguyên trên **full frame gốc đã decode, trước resize model**.
- Gốc tọa độ ở góc trên trái.
- Biểu diễn: `x`, `y`, `width`, `height`, `frame_width`, `frame_height`.
- Miền bao phủ là `[x, x + width)` và `[y, y + height)`.
- Ràng buộc: `x,y >= 0`, `width,height >= 1`, `x + width <= frame_width`,
  `y + height <= frame_height`.
- Full frame được chuẩn hóa thành `image/jpeg`; storage service tính SHA-256 trên chính bytes
  được ghi vào MinIO.

Không lưu tọa độ chuẩn hóa vì crop/annotate cần khớp chính xác object gốc. Nếu pipeline resize
trước detector, worker phải quy đổi bbox trở lại hệ tọa độ full frame trước khi ingest.

### 5. State machine của PersonTrack

Ba trạng thái bền vững:

```text
PENDING ──success──> READY
   │
   └──failure──> FAILED ──explicit retry──> PENDING
```

- `PENDING`: metadata đã được nhận nhưng ít nhất một bước lưu trữ/chứng thực chưa hoàn tất.
- `READY`: PostgreSQL đã xác nhận full frame và vector tồn tại đúng checksum/version.
- `FAILED`: lỗi đã được ghi nhận; không được tìm kiếm. Retry tường minh đưa về `PENDING`.
- Gán lại cùng trạng thái là no-op idempotent.
- `READY` là terminal trong phiên bản đầu. Không có `DELETING` vì đồ án chưa tự động xóa
  track; thêm deletion workflow về sau cần ADR mới.

Milvus có field `published`. Search chỉ xét `published == true`, sau đó hydrate và kiểm tra
`PersonTrack.state == READY` ở PostgreSQL. Hai lớp kiểm tra ngăn vector dở dang/stale trở
thành kết quả.

### 6. Vòng đời User, Camera và dữ liệu lịch sử

- User dùng trạng thái `ACTIVE`, `LOCKED`, `INACTIVE`, `DELETED` (soft delete).
- Camera dùng `ACTIVE`, `INACTIVE`, `RETIRED`; thao tác “xóa/loại khỏi vận hành” chuyển sang
  `RETIRED`.
- Không hard-delete User/Camera bằng API nghiệp vụ.
- Foreign key lịch sử dùng `RESTRICT/NO ACTION`; không cascade xóa Case, CaseResult,
  PersonTrack hoặc AuditLog.
- Username và mã Camera/Area đã dùng vẫn được giữ để tránh tái sử dụng gây nhập nhằng.
- CaseResult snapshot tên camera, khu vực và thời gian xuất hiện tại lúc lưu.
- Dữ liệu track được CaseResult tham chiếu không được cleanup tự động.
- Trong phạm vi đồ án, cả track chưa được Case tham chiếu cũng được giữ; **không có retention
  job tự xóa**. Thay đổi chính sách cần ADR và backup trước khi áp dụng.

### 7. MinIO naming và isolation

- Môi trường local/demo dùng **một MinIO endpoint** để giảm RAM.
- Bucket ứng dụng cố định: `person-search-frames`.
- Milvus dùng bucket/namespace nội bộ riêng do deployment Milvus quản lý; ứng dụng không
  hard-code tên bucket nội bộ đó.
- Application service account chỉ có quyền cần thiết trên `person-search-frames` và không có
  quyền đối với bucket Milvus. Milvus dùng credential riêng.
- Bucket ứng dụng không anonymous và không được frontend truy cập trực tiếp.

Object key version 1:

```text
tracks/v1/{camera_uuid}/{YYYY}/{MM}/{DD}/{track_uuid}/representative.jpg
```

Ngày trong key lấy từ `appeared_at_utc`. Object là immutable: ghi lại cùng key/chính checksum
là idempotent; khác checksum là conflict.

### 8. RaSa vector profile và Milvus naming

Phiên bản đầu dùng checkpoint **RaSa CUHK-PEDES chính thức** với profile:

| Thuộc tính | Giá trị |
| --- | --- |
| `encoder_version` | `rasa_cuhk_pedes_v1` |
| Dimension | `256` |
| Normalization | L2 normalized |
| Milvus metric | `IP` (inner product) |
| Scalar time | Unix epoch milliseconds |

Repository RaSa chính thức cấu hình `embed_dim: 256`; luồng retrieval chuẩn hóa cả image và
text embedding rồi tính tích vô hướng. Checkpoint artifact phải có SHA-256 được cấu hình và
kiểm tra lúc worker khởi động. Hash là định danh artifact triển khai, không được thay đổi dưới
cùng `encoder_version`.

Collection vật lý:

```text
person_track_embeddings_{encoder_version}
```

Collection đầu tiên là `person_track_embeddings_rasa_cuhk_pedes_v1`. Alias ổn định mà
application dùng là `person_track_embeddings_active`. Đổi checkpoint/dimension tạo collection
mới, lập chỉ mục lại và chuyển alias sau khi kiểm chứng; không trộn vector khác version trong
cùng collection.

### 9. Write ordering và tính nhất quán

Write flow chuẩn:

1. Worker gửi `TrackIngestionRequest` hợp lệ với UUIDv4, timeline, bbox, JPEG và vector.
2. Transaction PostgreSQL tạo `PersonTrack(PENDING)` và outbox/work item. Nếu `track_id` đã
   tồn tại, storage service kiểm tra idempotency thay vì tạo bản ghi mới.
3. Ghi MinIO object bằng key xác định, kiểm tra content length và SHA-256 qua `HEAD`.
4. Upsert Milvus row với `published=false`, đúng dimension/version/filter metadata.
5. Transaction PostgreSQL lưu object key/checksum/vector metadata và chuyển track `READY`.
6. Cập nhật Milvus `published=true`. Chỉ lúc này track là ứng viên search.
7. Đánh dấu outbox hoàn tất và trả kết quả idempotent cho worker.

Nếu process chết ở bất kỳ bước nào, track không được trả về vì chưa đồng thời thỏa
`published=true` và `PostgreSQL READY`. Retry dùng cùng `track_id`. Reconciliation ở STO-12
kiểm tra và sửa `PENDING/FAILED`, object/vector thiếu hoặc trạng thái publish lệch.

Không có distributed transaction. Tính nhất quán đạt bằng state machine, idempotency, outbox,
write verification và reconciliation.

### 10. Backup và khả năng tái tạo

- PostgreSQL và bucket `person-search-frames` là dữ liệu phải backup cho demo.
- Milvus cũng được backup để rút ngắn phục hồi; về lý thuyết có thể re-index từ embedding
  nguồn, nhưng không giả định video/checkpoint luôn còn sẵn.
- Không coi video upload tạm thời là backup.
- Runbook, RPO/RTO và restore drill được hiện thực ở STO-19.

## Hệ quả

### Tích cực

- PostgreSQL là điểm kiểm tra quyền duy nhất, giảm nguy cơ Milvus filter trở thành cơ chế
  authorization không đầy đủ.
- UUID và deterministic key giúp retry an toàn.
- Tách `appeared_at` khỏi ingestion time giữ đúng ngữ nghĩa tìm theo thời gian.
- Versioned collection ngăn trộn embedding không tương thích.
- Một MinIO endpoint giảm tài nguyên demo nhưng credential/bucket vẫn cô lập.

### Đánh đổi

- Có các cửa sổ nhất quán cuối cùng giữa ba kho; cần retry/reconciliation.
- Full frame JPEG là bất biến, nên sửa bbox không được ghi đè ảnh nhưng vẫn cần migration
  metadata nếu pipeline phát hiện sai.
- UUIDv4 không có locality theo thời gian; index timestamp phải được thiết kế đúng.
- Giữ toàn bộ track trong phạm vi đồ án làm tăng dung lượng nhưng tránh xóa nhầm dữ liệu.

## Phương án đã loại

- **Lưu mọi thứ trong PostgreSQL:** không phù hợp vector search và object ảnh lớn.
- **Milvus là nguồn sự thật:** không phù hợp Case, transaction và authorization quan hệ.
- **Bucket public/presigned URL mặc định:** dễ bỏ qua kiểm tra quyền backend.
- **UUID từ database:** worker không có ID ổn định trước MinIO/Milvus I/O.
- **Lưu Matching Score trong Case:** mâu thuẫn quyết định mới nhất; score chỉ thuộc lượt search.
- **Một collection cho mọi checkpoint:** dimension/không gian vector có thể không tương thích.
- **Hard delete User/Camera:** phá vỡ lịch sử Case và audit.

## Nguồn kỹ thuật

- [RaSa repository chính thức](https://github.com/Flame-Chasers/RaSa)
- [RaSa CUHK-PEDES config](https://github.com/Flame-Chasers/RaSa/blob/master/configs/PS_cuhk_pedes.yaml)
- [RaSa retrieval implementation](https://github.com/Flame-Chasers/RaSa/blob/master/Retrieval.py)
