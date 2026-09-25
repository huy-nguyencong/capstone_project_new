# Kế hoạch thiết kế và hiện thực tầng lưu trữ dữ liệu

> Tài liệu làm việc cho ứng dụng tìm kiếm người qua camera. Mỗi task bên dưới là một đơn vị triển khai, review, kiểm thử và commit độc lập. Không chuyển sang task kế tiếp khi task hiện tại chưa được người thực hiện review và chấp thuận.

## 1. Mục tiêu

Xây dựng tầng lưu trữ có thể chạy và kiểm thử được cho ba nhóm dữ liệu:

- **PostgreSQL:** dữ liệu nghiệp vụ, phân quyền, camera, track, Case, cấu hình AI, job, audit log và trạng thái đồng bộ.
- **Milvus:** vector embedding của từng `PersonTrack` cùng các trường phục vụ lọc theo khu vực, camera và thời gian.
- **MinIO:** full frame đại diện của từng track. Person crop chỉ được tạo động từ full frame và bounding box.

Tầng lưu trữ phải bảo đảm các quy tắc đã chốt trong `architect.md`:

- Một camera thuộc đúng một khu vực và không được đổi khu vực sau khi tạo.
- Một Operator có đúng một khu vực hiện tại; backend luôn tự lấy khu vực này để giới hạn tìm kiếm.
- Một kết quả tìm kiếm đại diện cho một track, không phải một frame.
- `Matching Score` chỉ tồn tại trong response của lần tìm kiếm; không lưu vào `PersonTrack` hoặc `CaseResult`.
- Mỗi lần bấm lưu tạo một `CaseResult` mới, kể cả khi cùng track đã có trong Case.
- Case có đúng một Operator sở hữu, không gắn khu vực và không có trạng thái.
- Tài khoản/camera ngừng hoạt động không làm mất dữ liệu lịch sử được Case tham chiếu.
- Track chỉ được tìm kiếm khi metadata, full frame và vector đã được ghi hoàn chỉnh.

## 2. Nguồn yêu cầu và thứ tự ưu tiên

1. `files/architect.md` là nguồn quyết định mới nhất.
2. `files/usecase_detail.md` mô tả luồng chính, ngoại lệ và quyền của 15 use case.
3. `files/project_requirements.md` mô tả phạm vi nghiệp vụ tổng quát.

Nếu ba tài liệu mâu thuẫn, áp dụng quyết định trong `architect.md` và ghi lại khác biệt trong ADR hoặc changelog của task liên quan.

## 3. Công nghệ mặc định để lập kế hoạch

Các lựa chọn dưới đây là phương án mặc định, sẽ được khóa lại ở **STO-01** trước khi viết mã nghiệp vụ:

- Python 3.11+ và Flask.
- SQLAlchemy 2.x + Alembic + psycopg 3 cho PostgreSQL.
- `pymilvus` cho Milvus.
- MinIO Python SDK cho object storage.
- `pytest`, `pytest-cov` và test integration chạy trên Docker Compose.
- Docker Compose cho môi trường phát triển gồm PostgreSQL, Milvus Standalone và MinIO.
- Cấu hình bằng biến môi trường; repository không chứa mật khẩu thật.

Nếu máy demo không đủ tài nguyên cho Milvus Standalone, chỉ thay đổi phương án sau khi có số đo ở **STO-18**. Không âm thầm đổi công nghệ giữa chừng.

## 4. Cấu trúc thư mục đích dự kiến

```text
backend/
  pyproject.toml
  src/person_search/
    __init__.py
    config.py
    extensions.py
    domain/
    storage/
      postgres/
        models/
        repositories/
      milvus/
      minio/
    services/
  migrations/
  tests/
    unit/
    integration/
    e2e/
infra/
  compose.yaml
  env.example
scripts/
docs/
  storage/
```

Cấu trúc cuối cùng có thể được tinh chỉnh ở STO-00 nhưng phải tiếp tục giữ ranh giới giữa domain, adapter lưu trữ và service điều phối.

## 5. Quy trình thực hiện một task

Mỗi task tuân theo cùng một vòng lặp:

> **Trạng thái repository khi lập kế hoạch:** thư mục làm việc hiện chưa có metadata Git (`.git`). Trước commit đầu tiên, cần xác nhận đây là đúng repository rồi khởi tạo Git hoặc mở đúng thư mục repository theo chỉ dẫn của người thực hiện. Không tự khởi tạo repository hay tạo commit khi chưa được yêu cầu.

1. Chỉ triển khai đúng phạm vi task đang làm.
2. Cập nhật checkbox trạng thái và ghi chú quyết định trong tài liệu này.
3. Chạy các test bắt buộc của task, lưu lại câu lệnh và kết quả tóm tắt.
4. Dừng để người thực hiện review code, migration, schema và kết quả test.
5. Nếu review yêu cầu chỉnh sửa, tiếp tục trên cùng task; chưa bắt đầu task tiếp theo.
6. Khi review đạt và test chạy tốt, kiểm tra diff rồi tạo một commit riêng.
7. Gắn SHA commit vào bảng theo dõi và mới chuyển task sang `DONE`.

Trạng thái hợp lệ:

- `TODO`: chưa bắt đầu.
- `IN_PROGRESS`: đang triển khai hoặc đang sửa theo review.
- `READY_FOR_REVIEW`: đã triển khai và test, đang chờ người thực hiện review.
- `DONE`: đã review, test đạt và commit.
- `BLOCKED`: có trở ngại cần quyết định hoặc phụ thuộc bên ngoài.

### Definition of Done cho mọi task

- Không còn thay đổi ngoài phạm vi task.
- Có test tương ứng với hành vi mới hoặc có giải thích vì sao task chỉ là tài liệu/cấu hình.
- Test cũ và test mới đều chạy đạt.
- Không có secret, ảnh/video thật hoặc dữ liệu nhạy cảm trong Git.
- Migration có đường nâng cấp rõ ràng; task thay schema phải kiểm tra trên database rỗng và database đã có migration trước đó.
- Tài liệu và ví dụ cấu hình được cập nhật khi interface hoặc cách chạy thay đổi.
- Người thực hiện đã review trước khi commit.

## 6. Bảng theo dõi tổng thể

| Task | Nội dung | Phụ thuộc | Trạng thái | Commit |
| --- | --- | --- | --- | --- |
| STO-00 | Khởi tạo skeleton và bộ lệnh kiểm thử | Không | DONE | `cc440d4` |
| STO-01 | Chốt kiến trúc lưu trữ và hợp đồng dữ liệu | STO-00 | DONE | `222c0ad` |
| STO-02 | Dựng hạ tầng Docker Compose | STO-01 | DONE | `aeb8203` |
| STO-03 | Cấu hình ứng dụng, kết nối và health check | STO-02 | DONE | `df1456b` |
| STO-04 | Schema PostgreSQL cho Area, User, Camera | STO-03 | DONE | `ba19a77` |
| STO-05 | Schema PostgreSQL cho AI config, job và PersonTrack | STO-04 | READY_FOR_REVIEW | — |
| STO-06 | Schema PostgreSQL cho Case, CaseResult và AuditLog | STO-05 | TODO | — |
| STO-07 | Ràng buộc, index, seed và kiểm thử migration | STO-06 | TODO | — |
| STO-08 | Repository và transaction cho PostgreSQL | STO-07 | TODO | — |
| STO-09 | Adapter lưu full frame trên MinIO | STO-03 | TODO | — |
| STO-10 | Collection và adapter vector trên Milvus | STO-03 | TODO | — |
| STO-11 | Điều phối ghi track xuyên ba kho dữ liệu | STO-08, STO-09, STO-10 | TODO | — |
| STO-12 | Retry, reconciliation và xử lý dữ liệu dở dang | STO-11 | TODO | — |
| STO-13 | Truy vấn vector có lọc và kiểm tra quyền | STO-11 | TODO | — |
| STO-14 | Đọc ảnh, crop động và kiểm tra quyền truy cập | STO-11 | TODO | — |
| STO-15 | Lưu CaseResult và thống kê Viewer | STO-08, STO-14 | TODO | — |
| STO-16 | Audit log và trạng thái vận hành lưu trữ | STO-08, STO-12 | TODO | — |
| STO-17 | Kiểm thử tích hợp và E2E toàn luồng | STO-13 đến STO-16 | TODO | — |
| STO-18 | Đo hiệu năng, tài nguyên và dung lượng | STO-17 | TODO | — |
| STO-19 | Backup, restore, bảo mật và runbook | STO-18 | TODO | — |

## 7. Chi tiết từng task

### STO-00 — Khởi tạo skeleton và bộ lệnh kiểm thử

**Mục tiêu:** tạo nền tảng tối thiểu để các task sau có cùng cấu trúc và cách chạy.

**Phạm vi thực hiện:**

- Tạo cấu trúc `backend`, `infra`, `scripts`, `docs/storage`.
- Khởi tạo package Python và Flask application factory tối thiểu.
- Khai báo dependency runtime/dev theo một cơ chế duy nhất trong `pyproject.toml`.
- Cấu hình `pytest`, marker `unit`, `integration`, `e2e` và coverage.
- Thêm `.gitignore`, `env.example` và lệnh kiểm tra format/lint/test thống nhất.
- Thêm một test smoke không truy cập dịch vụ ngoài.
- Ghi rõ cách chạy trên PowerShell và môi trường CI/Linux.

**Không làm trong task này:** model SQLAlchemy, migration, kết nối thật đến PostgreSQL/Milvus/MinIO.

**Kiểm thử:**

```powershell
python -m pytest -m unit
python -m compileall backend/src
```

**Tiêu chí chấp nhận:** package import được, application factory tạo app thành công, test smoke đạt từ repository sạch.

**Điểm cần review:** tên package, phiên bản Python, dependency manager và cấu trúc thư mục.

**Commit đề xuất:** `chore: bootstrap backend storage project`

---

### STO-01 — Chốt kiến trúc lưu trữ và hợp đồng dữ liệu

**Mục tiêu:** loại bỏ các quyết định mơ hồ trước khi tạo schema.

**Phạm vi thực hiện:**

- Viết ADR mô tả vai trò của PostgreSQL, Milvus và MinIO.
- Chốt ID dùng xuyên hệ thống, đề xuất UUID do ứng dụng tạo.
- Chốt chuẩn timestamp: lưu UTC, trả về ISO 8601; phân biệt thời gian ingest và timestamp trong video.
- Chốt biểu diễn bounding box, đề xuất `x`, `y`, `width`, `height` theo pixel kèm kích thước frame để kiểm tra biên.
- Chốt state machine của track: `PENDING`, `READY`, `FAILED`, `DELETING` nếu cần.
- Chốt chính sách soft-delete/disable cho User và Camera; không dùng cascade delete làm mất Case/track lịch sử.
- Chốt naming cho bucket/object key MinIO và collection/alias Milvus.
- Chốt một instance MinIO dùng bucket tách biệt hay hai instance. Phương án mặc định cho đồ án: một endpoint, bucket ứng dụng riêng và credential/policy riêng.
- Viết hợp đồng dữ liệu giữa AI worker và storage service cho thao tác ghi track.

**Kiểm thử:** review tài liệu bằng checklist; thêm test contract dạng schema nếu payload được định nghĩa bằng dataclass/Pydantic.

**Tiêu chí chấp nhận:** không còn câu hỏi chưa quyết định về ID, timestamp, bbox, trạng thái track, xóa dữ liệu, tên collection/bucket và write ordering.

**Điểm cần review:** các quyết định có phù hợp với máy demo, khả năng khôi phục và quy tắc phân quyền hay không.

**Commit đề xuất:** `docs: define storage architecture and contracts`

---

### STO-02 — Dựng hạ tầng Docker Compose

**Mục tiêu:** cung cấp môi trường phát triển tái lập được cho ba kho dữ liệu.

**Phạm vi thực hiện:**

- Thêm PostgreSQL, Milvus Standalone và MinIO vào `infra/compose.yaml` cùng dependency Milvus cần thiết.
- Pin phiên bản image; không dùng `latest`.
- Khai báo named volume, network nội bộ, health check và port phát triển.
- Tạo bucket ứng dụng private, user/policy giới hạn đúng bucket; không công khai object.
- Chuẩn bị biến môi trường mẫu, không commit password thật.
- Thêm script `up`, `down`, `status`, `logs` theo cách chạy đa nền tảng hoặc tài liệu PowerShell tương đương.
- Ghi mức RAM/disk dự kiến ban đầu và cách dừng dịch vụ an toàn.

**Kiểm thử:**

```powershell
docker compose -f infra/compose.yaml config
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

Sau khi các service healthy, chạy smoke check kết nối riêng cho PostgreSQL, Milvus và MinIO.

**Tiêu chí chấp nhận:** máy mới có Docker có thể dựng toàn bộ stack từ `env.example`; các volume tồn tại sau restart; bucket ứng dụng không anonymous.

**Điểm cần review:** port, image version, dung lượng volume, việc dùng chung MinIO và tổng RAM idle.

**Commit đề xuất:** `infra: add local storage stack`

---

### STO-03 — Cấu hình ứng dụng, kết nối và health check

**Mục tiêu:** ứng dụng tạo và đóng kết nối đúng cách, đồng thời phân biệt trạng thái từng kho dữ liệu.

**Phạm vi thực hiện:**

- Tạo lớp cấu hình typed cho PostgreSQL, Milvus và MinIO.
- Validate biến môi trường bắt buộc ngay khi khởi động.
- Tạo SQLAlchemy engine/session factory với pool có giới hạn.
- Tạo factory/client wrapper cho Milvus và MinIO; không dùng global client khó test.
- Thêm health check chi tiết và readiness check tổng hợp.
- Che password/token khỏi log và thông báo lỗi.
- Bảo đảm test có thể inject fake client.

**Kiểm thử:**

- Unit test parse cấu hình đúng/sai và redaction secret.
- Integration test mở/đóng kết nối tới từng service.
- Dừng lần lượt từng service để xác nhận health check báo đúng thành phần lỗi.

**Tiêu chí chấp nhận:** lỗi PostgreSQL không bị báo thành lỗi Milvus; app không được đánh dấu ready nếu dependency bắt buộc chưa sẵn sàng; không rò secret trong log test.

**Commit đề xuất:** `feat: add storage configuration and health checks`

---

### STO-04 — Schema PostgreSQL cho Area, User và Camera

**Mục tiêu:** hiện thực nền dữ liệu phục vụ phân quyền khu vực và camera.

**Bảng dự kiến:**

- `areas`: `id`, `code`, `name`, timestamp; `code` unique và ổn định.
- `users`: username unique, password hash, display name, role, status, `assigned_area_id`, timestamp.
- `cameras`: `area_id`, name, RTSP URL/credential được bảo vệ hoặc tham chiếu secret, trạng thái vận hành, RTSP status, `ai_enabled`, timestamp.

**Ràng buộc bắt buộc:**

- Operator phải có đúng một `assigned_area_id`; Admin/Viewer không dùng area để mở rộng quyền tìm kiếm.
- Camera phải có `area_id` khi tạo.
- `Camera.area_id` bất biến sau khi tạo, được chặn cả ở service và database.
- RTSP có thể để trống để camera logic vẫn xử lý file video trong demo.
- Xóa/ngừng hoạt động là thay đổi trạng thái; không cascade xóa lịch sử.

**Kiểm thử:**

- Migration upgrade/downgrade trên database rỗng.
- Tạo Operator không area và nhiều area phải thất bại theo contract.
- Sửa area của camera bằng repository và SQL trực tiếp đều bị từ chối.
- User/camera inactive vẫn giữ được khóa ngoại lịch sử.

**Tiêu chí chấp nhận:** schema thể hiện đúng quy tắc khu vực, không dựa riêng vào UI.

**Commit đề xuất:** `feat(db): add area user and camera schema`

---

### STO-05 — Schema PostgreSQL cho AI config, job và PersonTrack

**Mục tiêu:** lưu nguồn gốc, trạng thái và metadata của dữ liệu AI.

**Bảng dự kiến:**

- `ai_config_versions`: Detector, Tracker, encoder/checkpoint version, trạng thái áp dụng và timestamp.
- `processing_jobs`: nguồn `FILE`/`RTSP`, camera, trạng thái, sampling interval, progress, lỗi, thời gian bắt đầu/kết thúc.
- `person_tracks`: camera, job, thời gian xuất hiện, source frame index/timestamp, bbox, kích thước frame, MinIO key, checksum, encoder/config version, `index_status`, lỗi và timestamp.
- `storage_outbox_events` hoặc bảng công việc tương đương để retry các bước ghi ngoài PostgreSQL.

**Ràng buộc bắt buộc:**

- `sampling_interval > 0`.
- Bbox có kích thước dương và nằm trong giới hạn frame.
- `ended_at >= started_at` khi cả hai có giá trị.
- Track chỉ `READY` khi có object key/checksum và vector đã được xác nhận.
- Lưu phiên bản encoder/checkpoint để không trộn vector khác không gian.
- `Matching Score` không xuất hiện trong schema.

**Kiểm thử:** migration, constraint test, state-transition test và test không thể tạo track `READY` thiếu dữ liệu.

**Tiêu chí chấp nhận:** từ một `track_id` có thể xác định camera/khu vực, job nguồn, bbox, full frame, cấu hình AI và phiên bản encoder.

**Commit đề xuất:** `feat(db): add processing and person track schema`

---

### STO-06 — Schema PostgreSQL cho Case, CaseResult và AuditLog

**Mục tiêu:** lưu nghiệp vụ Case mà không làm sai các quyết định mới nhất.

**Bảng dự kiến:**

- `cases`: title, note, `owner_user_id`, timestamp; không có `status`, không có `area_id`.
- `case_results`: ID riêng cho mỗi lần lưu, `case_id`, `track_id`, snapshot tên camera/khu vực/thời gian xuất hiện, `saved_at`.
- `audit_logs`: actor, event type, target type/id, result, timestamp và metadata JSON đã lọc secret.

**Ràng buộc bắt buộc:**

- Owner Case phải là Operator tại thời điểm tạo và lấy từ phiên, không nhận tùy ý từ client.
- Không đặt unique constraint trên `(case_id, track_id)`.
- Không có cột `matching_score` trong `cases` hoặc `case_results`.
- Không cascade xóa Case khi User bị khóa/ngừng hoạt động.
- Xóa một CaseResult không xóa PersonTrack, frame hoặc vector.

**Kiểm thử:**

- Lưu cùng track hai lần tạo hai `case_result_id`.
- Xóa một mục không ảnh hưởng mục còn lại.
- Không thể gán Case cho Viewer/Admin qua service contract.
- Khóa Operator không làm mất Case.
- Kiểm tra schema không có Matching Score.

**Tiêu chí chấp nhận:** dữ liệu Case vẫn xem được khi tài khoản/camera không còn hoạt động và phản ánh snapshot tại thời điểm lưu.

**Commit đề xuất:** `feat(db): add case and audit schema`

---

### STO-07 — Ràng buộc, index, seed và kiểm thử migration

**Mục tiêu:** hoàn thiện schema vật lý và chứng minh migration đáng tin cậy.

**Phạm vi thực hiện:**

- Thêm index cho username, area/camera, owner Case, `PersonTrack(camera_id, appeared_at)`, index status và job status.
- Đánh giá index partial cho track `READY` và dữ liệu active.
- Thêm trigger/ràng buộc database còn thiếu, đặc biệt camera area bất biến.
- Seed danh mục Area mẫu, registry Detector/Tracker hoặc admin dev theo cách idempotent; không seed secret mặc định cho production.
- Viết test migrate từ revision đầu đến head, downgrade theo phạm vi an toàn rồi upgrade lại.
- Xuất sơ đồ ER và data dictionary ngắn từ schema đã chốt.

**Kiểm thử:** chạy migration ít nhất trên database rỗng và database đã có dữ liệu hợp lệ; dùng `EXPLAIN` cho các truy vấn chính.

**Tiêu chí chấp nhận:** migration lặp lại an toàn trong môi trường test; index phục vụ đúng truy vấn thay vì thêm tùy ý.

**Commit đề xuất:** `feat(db): harden schema migrations and indexes`

---

### STO-08 — Repository và transaction cho PostgreSQL

**Mục tiêu:** tách nghiệp vụ khỏi SQLAlchemy và xác định biên transaction rõ ràng.

**Phạm vi thực hiện:**

- Repository cho Area/User/Camera, AI config/job/track, Case/CaseResult và AuditLog.
- Unit of Work hoặc transaction context quản lý commit/rollback.
- Query method luôn nhận actor/context cần thiết; không cung cấp method quá rộng làm bỏ qua quyền.
- Pagination ổn định cho danh sách user, camera, Case và audit log.
- Optimistic locking hoặc điều kiện version cho các bản ghi dễ cập nhật cạnh tranh.
- Mapping lỗi unique/FK/check constraint sang exception domain rõ nghĩa.

**Kiểm thử:** unit test bằng fake/mocked session cho nhánh lỗi và integration test với PostgreSQL thật cho transaction, rollback, concurrency cơ bản và pagination.

**Tiêu chí chấp nhận:** service không cần biết SQLAlchemy query chi tiết; thao tác thất bại không để transaction nửa chừng.

**Commit đề xuất:** `feat(db): implement postgres repositories and unit of work`

---

### STO-09 — Adapter lưu full frame trên MinIO

**Mục tiêu:** lưu/đọc/xóa object idempotent trong bucket private.

**Phạm vi thực hiện:**

- Thiết kế key ổn định, ví dụ `tracks/{camera_id}/{yyyy}/{mm}/{dd}/{track_id}/representative.jpg`.
- API adapter: `put_frame`, `get_frame`, `head_frame`, `delete_frame` và checksum verification.
- Validate MIME, kích thước byte, chiều rộng/cao và định dạng ảnh được hỗ trợ.
- Ghi metadata tối thiểu: track ID, checksum, content type; không chứa credential hoặc mô tả nhạy cảm.
- Không trả URL public. Nếu dùng presigned URL thì phải ngắn hạn và chỉ phát hành sau khi service kiểm tra quyền; phương án mặc định là stream qua Flask.
- Put cùng key/checksum phải idempotent; cùng key khác checksum phải báo conflict.

**Kiểm thử:**

- Unit test với fake client: retry, not-found, checksum mismatch.
- Integration test put/head/get/delete và quyền anonymous bị từ chối.
- Test object bị hỏng hoặc MIME giả.

**Tiêu chí chấp nhận:** round-trip giữ nguyên checksum; bucket không public; log không chứa access/secret key.

**Commit đề xuất:** `feat(storage): add private minio frame adapter`

---

### STO-10 — Collection và adapter vector trên Milvus

**Mục tiêu:** lưu và tìm vector theo track, có lọc metadata trước khi lấy top-k.

**Schema vector dự kiến:**

- Primary key `track_id`.
- Vector ảnh với dimension lấy từ checkpoint RaSa đã chốt.
- Scalar field: `area_id`, `camera_id`, thời gian xuất hiện dạng epoch, `encoder_version` và trạng thái cần thiết.
- Collection/alias versioned để tránh trộn vector khác dimension hoặc khác checkpoint.

**Phạm vi thực hiện:**

- Script tạo/kiểm tra collection idempotent.
- Adapter upsert, get-by-id, delete và search.
- Filter builder chỉ tạo expression từ dữ liệu đã validate; không nối chuỗi tùy ý từ request.
- Kiểm tra dimension, finite number, normalization policy và encoder version.
- Cấu hình index/search params có giá trị mặc định cho máy demo, nhưng tách khỏi code.
- Search trả `track_id` và score tạm thời; không ghi score vào PostgreSQL.

**Kiểm thử:**

- Unit test filter builder và vector validation.
- Integration test insert/upsert/search/delete.
- Chứng minh filter area/camera/time loại dữ liệu ngoài phạm vi **trước** top-k.
- Test vector sai dimension, NaN/Infinity và collection sai version.

**Tiêu chí chấp nhận:** cùng truy vấn nhưng area khác không bao giờ nhận track ngoài area; top-k chỉ tính trong tập đã lọc.

**Commit đề xuất:** `feat(storage): add milvus person track index`

---

### STO-11 — Điều phối ghi track xuyên ba kho dữ liệu

**Mục tiêu:** một track không xuất hiện trong tìm kiếm khi dữ liệu chưa hoàn chỉnh.

**Write flow mặc định:**

1. Tạo `PersonTrack` ở PostgreSQL với trạng thái `PENDING` và idempotency key.
2. Upload full frame lên MinIO, xác nhận checksum.
3. Upsert embedding và scalar metadata vào Milvus.
4. Cập nhật PostgreSQL thành `READY` trong transaction cuối.
5. Nếu bước ngoài database lỗi, ghi nguyên nhân và lịch retry; không trả track trong tìm kiếm.

**Phạm vi thực hiện:**

- Service `ingest_track` nhận payload theo contract STO-01.
- Idempotency theo track/job để retry không tạo bản ghi hoặc object trùng ngoài ý muốn.
- Ghi outbox/work item trong cùng transaction với trạng thái PostgreSQL.
- Xác định rõ lỗi retryable và non-retryable.
- Chặn transition không hợp lệ, ví dụ `READY → PENDING`.
- Log correlation ID nhưng không log raw image/vector.

**Kiểm thử:**

- Happy path chứng minh cả ba nơi có cùng `track_id`.
- Failure injection tại từng bước: PostgreSQL insert, MinIO put, Milvus upsert và final commit.
- Retry sau từng lỗi phải hội tụ về đúng một track/object/vector.
- Search không thấy track `PENDING` hoặc `FAILED`.

**Tiêu chí chấp nhận:** không có trạng thái mà PostgreSQL báo `READY` nhưng object/vector bắt buộc chưa tồn tại; retry không nhân bản dữ liệu.

**Commit đề xuất:** `feat(storage): coordinate durable person track ingestion`

---

### STO-12 — Retry, reconciliation và xử lý dữ liệu dở dang

**Mục tiêu:** phát hiện và khôi phục sai lệch do tiến trình chết hoặc dịch vụ tạm thời unavailable.

**Phạm vi thực hiện:**

- Worker/CLI retry outbox với exponential backoff, giới hạn số lần và dead-letter state.
- Reconciliation kiểm tra track `PENDING/FAILED` quá hạn.
- Kiểm tra chéo PostgreSQL ↔ MinIO ↔ Milvus theo batch có giới hạn.
- Phân loại orphan object/vector và missing object/vector.
- Mặc định chỉ báo cáo/dry-run; xóa dữ liệu orphan là chế độ tường minh và có audit.
- Không tự xóa track/frame/vector đang được CaseResult tham chiếu.

**Kiểm thử:** kill/restart worker giữa các bước, làm MinIO/Milvus unavailable, tạo orphan có chủ đích và xác nhận dry-run không thay đổi dữ liệu.

**Tiêu chí chấp nhận:** reconciliation đưa dữ liệu retryable về `READY` hoặc báo lỗi rõ ràng; không xóa nhầm dữ liệu Case.

**Commit đề xuất:** `feat(storage): add retry and reconciliation workflow`

---

### STO-13 — Truy vấn vector có lọc và kiểm tra quyền

**Mục tiêu:** hiện thực đường đọc phục vụ tìm kiếm mà không rò dữ liệu ngoài khu vực Operator.

**Phạm vi thực hiện:**

- Service nhận actor Operator, query embedding, camera/time filter tùy chọn và `top_k`.
- Chỉ chấp nhận `top_k` trong `{4, 8, 12, 16}`.
- Lấy `assigned_area_id` từ PostgreSQL theo phiên/actor, không tin `area_id` của client.
- Validate mọi camera filter thuộc area của Operator; camera ngoài quyền làm request thất bại.
- Gửi filter area/camera/time sang Milvus trước vector search.
- Hydrate kết quả từ PostgreSQL và chỉ giữ track `READY`.
- Recheck quyền và metadata ở PostgreSQL trước response để phòng vector index cũ/sai.
- Trả Matching Score trong DTO response; không persist score.

**Kiểm thử:**

- Operator A không thể nhận track area B dù gửi camera ID trực tiếp.
- Filter xảy ra trước top-k, không phải lấy top-k toàn cục rồi mới bỏ kết quả.
- `top_k` ngoài tập cho phép bị từ chối.
- Track bị disable camera nhưng thuộc lịch sử được xử lý theo policy đã chốt.
- Milvus trả ID stale/missing thì service bỏ qua và ghi metric cảnh báo.

**Tiêu chí chấp nhận:** không có đường gọi public nào bỏ qua PostgreSQL authorization; score chỉ có trong response.

**Commit đề xuất:** `feat(search): add authorized vector retrieval`

---

### STO-14 — Đọc ảnh, crop động và kiểm tra quyền truy cập

**Mục tiêu:** cung cấp ảnh kết quả mà không public MinIO và không lưu crop độc lập.

**Phạm vi thực hiện:**

- Service đọc full frame theo `track_id` sau khi kiểm tra quyền.
- Hai context quyền: kết quả tìm kiếm hiện tại của Operator và track đã nằm trong Case mà actor được phép xem.
- Crop ảnh động từ bbox với clamp/validation an toàn.
- Tạo full-frame preview có bounding box mà không ghi bản sao lâu dài mặc định.
- Xử lý object thiếu/hỏng: trả metadata và lỗi ảnh rõ ràng, không làm Case biến mất.
- Thiết lập content type, cache policy và giới hạn kích thước response.

**Kiểm thử:** bbox ở biên, bbox lỗi, ảnh thiếu/hỏng, Operator đổi khu vực vẫn xem ảnh trong Case cũ của chính mình, Viewer xem mọi Case, actor không quyền nhận 403/404 theo policy.

**Tiêu chí chấp nhận:** bucket vẫn private; không có endpoint nhận object key tùy ý; không tạo file person crop bền vững.

**Commit đề xuất:** `feat(storage): serve authorized track imagery`

---

### STO-15 — Lưu CaseResult và thống kê Viewer

**Mục tiêu:** hoàn thiện đường ghi/đọc Case dựa trên dữ liệu track đã lưu.

**Phạm vi thực hiện:**

- Tạo Case với owner lấy từ Operator hiện tại.
- Thêm track vào Case chỉ khi Operator sở hữu Case và track thuộc quyền tìm kiếm hiện tại tại thời điểm lưu.
- Snapshot camera name, area name và appeared time từ server.
- Mỗi lần thêm tạo một `CaseResult` mới; không deduplicate.
- Sửa title/note và xóa đúng `case_result_id`.
- Operator luôn xem Case của mình sau khi đổi area; Viewer xem toàn bộ Case chỉ đọc.
- Dashboard đếm số row `CaseResult`, bao gồm các mục lặp cùng track.

**Kiểm thử:** duplicate save, owner spoofing, thêm vào Case người khác, đổi area sau khi tạo Case, Viewer read-only, dashboard count và xóa một duplicate.

**Tiêu chí chấp nhận:** Case không lưu Matching Score; quyền xem ảnh Case dựa trên Case/owner chứ không bị mất do Operator đổi area.

**Commit đề xuất:** `feat(case): persist saved track results and viewer stats`

---

### STO-16 — Audit log và trạng thái vận hành lưu trữ

**Mục tiêu:** cung cấp khả năng truy vết và quan sát lỗi cho Admin.

**Phạm vi thực hiện:**

- Ghi audit event cho đăng nhập/đăng xuất, user, area Operator, camera, AI config, Case create/update và lỗi kỹ thuật quan trọng.
- Không ghi mỗi lượt tìm kiếm của Operator theo phạm vi hiện tại.
- Chuẩn hóa event type, actor snapshot, target và result.
- Redact password, RTSP credential, token, raw vector và raw image.
- Query audit log theo thời gian, actor, event type với pagination ổn định.
- Metric/trạng thái tối thiểu: số track theo status, outbox pending/dead, lỗi MinIO/Milvus và thời gian xử lý.

**Kiểm thử:** event thành công/thất bại, filter/pagination, redaction secret và xác nhận search request không tạo audit event nghiệp vụ.

**Tiêu chí chấp nhận:** Admin phân biệt được lỗi từng storage component; audit log không trở thành nơi rò dữ liệu nhạy cảm.

**Commit đề xuất:** `feat(storage): add audit and operational visibility`

---

### STO-17 — Kiểm thử tích hợp và E2E toàn luồng

**Mục tiêu:** chứng minh các thành phần hoạt động cùng nhau theo use case chính.

**Kịch bản E2E bắt buộc:**

1. Seed hai area, camera và Operator ở hai area khác nhau.
2. Tạo một processing job gắn camera.
3. Ghi full frame + bbox + embedding thành track `READY`.
4. Tìm bằng vector và chỉ nhận kết quả thuộc area của Operator.
5. Lấy crop/full frame qua service có quyền.
6. Tạo Case, lưu cùng track hai lần.
7. Đổi area của Operator; tìm kiếm mới theo area mới nhưng Case cũ vẫn xem được.
8. Viewer xem Case và dashboard đếm hai CaseResult.
9. Làm MinIO hoặc Milvus unavailable và xác nhận error/retry đúng.

**Phạm vi thực hiện:** fixture deterministic, ảnh giả nhỏ và vector nhỏ hoặc collection test riêng; không đưa video/dataset thật vào repository.

**Kiểm thử:**

```powershell
python -m pytest -m unit
python -m pytest -m integration
python -m pytest -m e2e
```

**Tiêu chí chấp nhận:** test chạy lặp lại được từ database/volume test sạch; không phụ thuộc thứ tự test; failure output chỉ rõ storage component gây lỗi.

**Commit đề xuất:** `test: cover storage workflow end to end`

---

### STO-18 — Đo hiệu năng, tài nguyên và dung lượng

**Mục tiêu:** xác nhận kiến trúc phù hợp máy demo và lập kế hoạch dung lượng dựa trên số đo.

**Phạm vi đo:**

- RAM/CPU/disk khi stack idle và khi ingest/search.
- Throughput ghi track, p50/p95 thời gian search và thời gian hydrate ảnh.
- Dung lượng trung bình của full frame, metadata PostgreSQL và vector trên mỗi track.
- So sánh index/search params Milvus phù hợp quy mô dữ liệu demo.
- Chạy với dữ liệu tổng hợp theo các mốc nhỏ/trung bình gần dự kiến 7 video.
- Ghi rõ cấu hình máy, số bản ghi, dimension, concurrency và kết quả để có thể lặp lại.

**Kiểm thử/chấp nhận:** định nghĩa ngưỡng sau baseline đầu tiên; tối thiểu hệ thống không OOM trên máy demo, search ổn định và đủ dung lượng để lập chỉ mục 7 video. Nếu không đạt, tạo ADR điều chỉnh thay vì tối ưu không có số đo.

**Commit đề xuất:** `perf: document storage capacity baseline`

---

### STO-19 — Backup, restore, bảo mật và runbook

**Mục tiêu:** có thể khôi phục môi trường demo và vận hành an toàn ở mức đồ án.

**Phạm vi thực hiện:**

- Backup/restore PostgreSQL có version và checksum.
- Backup bucket full frame hoặc quy trình export/sync phù hợp.
- Backup/restore Milvus theo công cụ được phiên bản đang dùng hỗ trợ; nếu vector có thể tái tạo, ghi rõ chi phí và quy trình re-index.
- Xác định thứ tự restore để PostgreSQL, MinIO và Milvus hội tụ; chạy reconciliation sau restore.
- Rotation credential, least privilege, network exposure và TLS cho môi trường ngoài local.
- Runbook: start/stop, migrate, seed, health check, retry dead-letter, reconcile dry-run, backup, restore và xử lý disk đầy.
- Ghi RPO/RTO thực tế cho phạm vi demo.

**Kiểm thử:** khôi phục vào stack trống, chạy integrity/reconciliation, sau đó chạy lại kịch bản tìm kiếm → xem ảnh → mở Case.

**Tiêu chí chấp nhận:** bản backup được chứng minh bằng restore test; không chỉ có script chưa từng chạy.

**Commit đề xuất:** `docs: add storage recovery and security runbook`

## 8. Ma trận kiểm thử tổng thể

| Loại test | Mục đích | Tần suất |
| --- | --- | --- |
| Unit | Validation, state transition, filter builder, quyền, mapping lỗi | Mỗi task/code change |
| Migration | Upgrade/downgrade, constraint, dữ liệu có sẵn | Mỗi thay đổi schema |
| Integration PostgreSQL | Transaction, FK, index, concurrency | STO-04 trở đi |
| Integration MinIO | Quyền bucket, checksum, object lifecycle | STO-09 trở đi |
| Integration Milvus | Collection, dimension, filter-before-top-k | STO-10 trở đi |
| Failure injection | Dịch vụ chết giữa write flow, retry/idempotency | STO-11 và STO-12 |
| Authorization | Area, owner Case, Viewer read-only, image access | STO-13 đến STO-15 |
| E2E | Track → search → image → Case → Viewer | STO-17 và trước release |
| Performance | RAM/disk/latency/throughput trên máy demo | STO-18 và khi đổi model/index |
| Restore drill | Khôi phục và reconciliation | STO-19 và trước buổi demo |

## 9. Checklist review trước mỗi commit

- [ ] Task đang ở `READY_FOR_REVIEW` và chỉ chứa thay đổi thuộc task đó.
- [ ] Đã xem `git diff --check` và diff đầy đủ.
- [ ] Không có file `.env`, credential, dữ liệu thật hoặc volume Docker được stage.
- [ ] Đã chạy đúng unit/integration/E2E test được task yêu cầu.
- [ ] Đã lưu kết quả test tóm tắt trong phần nhật ký bên dưới.
- [ ] Migration và rollback đã được review nếu task thay schema.
- [ ] Quy tắc quyền được kiểm tra tại backend/storage service, không chỉ ở UI.
- [ ] Người thực hiện xác nhận chấp nhận kết quả.
- [ ] Chỉ sau các bước trên mới commit và điền SHA vào bảng theo dõi.

## 10. Nhật ký thực hiện

Mỗi lần làm task, thêm một mục theo mẫu:

```text
### YYYY-MM-DD — STO-XX
- Trạng thái: READY_FOR_REVIEW | DONE | BLOCKED
- Thay đổi chính:
- File quan trọng:
- Test đã chạy:
- Kết quả:
- Điểm cần người thực hiện review:
- Quyết định/chỉnh sửa sau review:
- Commit SHA (chỉ điền sau khi DONE):
```

### 2026-09-25 — STO-00

- Trạng thái: `DONE`.
- Thay đổi chính: bổ sung namespace domain/services/storage cho PostgreSQL, Milvus và MinIO; tạo ranh giới migrations, infra, scripts và tài liệu storage; thêm bộ lệnh kiểm tra đa nền tảng và smoke test không cần dịch vụ ngoài.
- File quan trọng: `backend/src/person_search/storage/`, `backend/tests/unit/test_storage_skeleton.py`, `scripts/check.ps1`, `scripts/check.sh`, `docs/storage/README.md`, `infra/README.md`.
- Test đã chạy: PowerShell `scripts/check.ps1`; Git Bash `scripts/check.sh`; pytest với coverage; `git diff --check`.
- Kết quả: 23 test đạt; coverage 79%; Ruff sạch; toàn bộ source compile thành công; package storage import được khi PostgreSQL/Milvus/MinIO không chạy.
- Điểm cần người thực hiện review: tên các namespace, vị trí migrations, hai script kiểm tra và việc chưa thêm dependency storage trong STO-00.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chuyển sang STO-01 sau khi commit.
- Commit SHA: `cc440d4`.

### 2026-09-25 — STO-01

- Trạng thái: `DONE`.
- Thay đổi chính: chấp thuận ADR-0001 cho vai trò ba kho, UUIDv4, UTC/source timeline, bbox pixel, state machine, soft-delete, naming MinIO/Milvus, RaSa vector profile và write ordering; bổ sung contract executable giữa AI worker và storage service.
- File quan trọng: `docs/storage/adr/0001-storage-architecture-and-track-contract.md`, `docs/storage/track-ingestion-contract.md`, `backend/src/person_search/storage/contracts.py`, `backend/tests/unit/test_storage_contracts.py`.
- Test đã chạy: PowerShell `scripts/check.ps1`; pytest với branch coverage; Git Bash syntax check; `git diff --check`.
- Kết quả: 64 test đạt; coverage tổng 89%, contract module 95%; Ruff sạch; compile thành công.
- Điểm cần người thực hiện review: UUIDv4, retention không tự xóa, một MinIO endpoint với bucket/credential tách biệt, RaSa CUHK-PEDES 256 chiều + IP và write flow `PENDING → READY/FAILED`.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và chuyển sang STO-02.
- Commit SHA: `222c0ad`.

### 2026-09-25 — STO-02

- Trạng thái: `DONE`.
- Thay đổi chính: dựng stack local gồm PostgreSQL 17.11, Milvus 2.6.24, etcd 3.5.25 và MinIO; pin toàn bộ image, dùng named volume và network bridge riêng; chỉ publish port trên loopback; bootstrap bucket private `person-search-frames` cùng app user/policy giới hạn đúng bucket; bổ sung script validate/up/down/status/logs/smoke cho PowerShell và POSIX shell.
- File quan trọng: `infra/compose.yaml`, `infra/.env.example`, `infra/minio/app-policy.json`, `infra/minio/bootstrap.sh`, `infra/minio/smoke.sh`, `infra/README.md`, `scripts/storage.ps1`, `scripts/storage.sh`.
- Test đã chạy: Compose `config --quiet`; dựng thật bằng `scripts/storage.ps1 up`; `ps` và smoke riêng cho PostgreSQL/Milvus/MinIO; anonymous HTTP request; một vòng `down`/`up`; so sánh identity bốn named volume; parse PowerShell; `bash -n` cho ba shell script; JSON parse policy; `scripts/check.ps1`; `git diff --check`.
- Kết quả: PostgreSQL, etcd, MinIO và Milvus đều healthy; bootstrap exit code 0; PostgreSQL nhận kết nối, Milvus health trả `OK`, app credential đọc được bucket ứng dụng nhưng không truy cập được bucket Milvus, anonymous request trả HTTP 403; port host chỉ bind `127.0.0.1`; bốn volume giữ nguyên qua restart; 64 unit test đạt, Ruff và compile sạch.
- Điểm cần người thực hiện review: các port mặc định, mức RAM tối thiểu 8 GB/khuyến nghị 16 GB, policy cho phép Get/Put/Delete trong bucket ứng dụng, và việc giữ bộ MinIO/etcd đúng manifest standalone chính thức của Milvus 2.6.24 cho môi trường local.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và yêu cầu chuyển sang STO-03.
- Commit SHA: `aeb8203`.

### 2026-09-25 — STO-03

- Trạng thái: `DONE`.
- Thay đổi chính: bổ sung cấu hình typed và fail-fast cho PostgreSQL/Milvus/MinIO; SQLAlchemy engine/session factory với pool và timeout giới hạn; client wrapper Milvus/MinIO lazy, injectable và có lifecycle close; health aggregator cô lập lỗi từng kho, redaction secret, endpoint `/health/ready` và `/health/storage`; cấu hình development qua `.env` và integration test kết nối thật.
- File quan trọng: `backend/src/person_search/config.py`, `backend/src/person_search/storage/runtime.py`, `backend/src/person_search/storage/health.py`, ba module `storage/*/client.py`, `backend/src/person_search/api/health.py`, `backend/tests/unit/test_storage_configuration.py`, `backend/tests/unit/test_storage_clients.py`, `backend/tests/integration/test_storage_connections.py`.
- Test đã chạy: `scripts/check.ps1`; pytest unit; integration test với stack thật; failure injection lần lượt dừng/khởi động lại PostgreSQL, Milvus và MinIO; pytest branch coverage; Ruff; compileall; `git diff --check`.
- Kết quả: 78 unit test đạt; 2 integration test healthy đạt; ba failure-injection test đều trả 503 và chỉ đánh dấu đúng component bị dừng; stack được phục hồi healthy; tổng 80 test đạt, 1 test failure-injection được skip trong lượt coverage chuẩn; branch coverage 92%; Ruff và compile sạch; không có secret trong response/log test.
- Điểm cần người thực hiện review: tên biến môi trường, pool mặc định `5 + 5`, timeout kết nối 3 giây, việc client Milvus/MinIO khởi tạo lazy, schema JSON của hai health endpoint và lifecycle đóng bằng runtime/`atexit`.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và yêu cầu chuyển sang STO-04.
- Commit SHA: `df1456b`.

### 2026-09-25 — STO-04

- Trạng thái: `DONE`.
- Thay đổi chính: thêm Alembic environment và migration đầu tiên; model SQLAlchemy cho Area/User/Camera với UUIDv4, enum trạng thái, timestamp UTC, role–area check constraint, foreign key `RESTRICT`, RTSP secret reference; trigger database và guard ORM khóa `Area.code`, `Camera.code` và `Camera.area_id`; trigger đồng bộ `updated_at` cho cả ORM/raw SQL.
- File quan trọng: `backend/alembic.ini`, `backend/migrations/versions/20260925_0001_area_user_camera.py`, `backend/src/person_search/storage/postgres/models/`, `backend/tests/integration/test_identity_schema.py`, `docs/storage/postgres-identity-schema.md`.
- Test đã chạy: `scripts/check.ps1`; 81 unit test; migration integration trên database dùng một lần; `downgrade base → upgrade head → alembic check → constraint tests → downgrade base`; Ruff; compileall; branch coverage; `git diff --check`.
- Kết quả: 81 unit test đạt; migration integration đạt; Alembic không phát hiện schema drift; Operator thiếu area và Admin có area bị từ chối; Camera thiếu area hoặc RTSP nhúng credential bị từ chối; đổi Camera area bị chặn ở ORM lẫn raw SQL; đổi Area code bị chặn; xóa Area đang được User/Camera tham chiếu bị FK `RESTRICT` chặn; inactive row vẫn giữ area FK; downgrade xóa sạch ba bảng/type; unit branch coverage tổng 89%.
- Điểm cần người thực hiện review: enum/status, quy tắc uppercase và bất biến của code, role–area constraint, việc chỉ lưu `rtsp_secret_ref`, trigger PostgreSQL, tên migration và giới hạn STO-04 chưa có repository nghiệp vụ đầy đủ.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và yêu cầu chuyển sang STO-05.
- Commit SHA: `ba19a77`.

### 2026-09-25 — STO-05

- Trạng thái: `READY_FOR_REVIEW`.
- Thay đổi chính: thêm model và migration cho phiên bản cấu hình AI, processing job, PersonTrack và transactional outbox; bảo vệ bbox/timeline/progress bằng constraint; khóa state machine track ở cả ORM và PostgreSQL; chỉ cho phép `READY` khi MinIO artifact và vector index đã được xác nhận; giữ đầy đủ lineage camera/area/job/config/encoder và không lưu Matching Score.
- File quan trọng: `backend/migrations/versions/20260925_0002_processing_tracks.py`, `backend/src/person_search/storage/postgres/models/ai_config.py`, `processing_job.py`, `person_track.py`, `outbox.py`, `backend/tests/integration/test_processing_schema.py`, `docs/storage/postgres-processing-schema.md`.
- Test đã chạy: Ruff; 85 unit test; migration integration trên database dùng một lần; `downgrade base → upgrade head → alembic check → constraint/state-transition tests → downgrade 0001 → downgrade base`.
- Kết quả: unit và integration đều đạt; Alembic không phát hiện schema drift; PostgreSQL từ chối sampling interval không dương, bbox vượt frame, track khởi tạo ở `READY`, `READY` thiếu artifact và chuyển ngược `READY → FAILED`; rollback giữ schema STO-04 rồi xóa sạch về base.
- Điểm cần người thực hiện review: bộ field lineage, quy tắc một AI config `ACTIVE`, state machine `PENDING → READY/FAILED`, retry `FAILED → PENDING`, `READY` là trạng thái cuối, payload JSONB và unique `(track_id, event_type)` của outbox.
- Quyết định/chỉnh sửa sau review: chờ review.
- Commit SHA: —.

## 11. Các quyết định đã khóa ở STO-01

- PostgreSQL là database nghiệp vụ cuối cùng và là nguồn sự thật về quyền/trạng thái.
- Local/demo dùng một MinIO endpoint; bucket ứng dụng `person-search-frames` và credential được tách khỏi bucket/credential nội bộ Milvus.
- Application tạo UUIDv4 trước mọi I/O; PostgreSQL dùng `uuid`, Milvus/object key dùng chuỗi canonical.
- Phiên bản đầu dùng profile `rasa_cuhk_pedes_v1`, vector 256 chiều, L2-normalized và metric IP; checkpoint SHA-256 bắt buộc được kiểm tra lúc worker khởi động.
- Mỗi encoder version có collection vật lý riêng; application dùng alias `person_track_embeddings_active`.
- Bbox dùng pixel nguyên trên full frame gốc; source offset dùng milliseconds, absolute time dùng UTC.
- Trong phạm vi đồ án không có retention job tự xóa track, kể cả track chưa được Case tham chiếu.
- PostgreSQL và bucket frame bắt buộc backup; Milvus được backup để phục hồi nhanh và không mặc định có thể tái tạo nếu video/checkpoint không còn.

Chi tiết và hệ quả của từng quyết định nằm trong ADR-0001. Thay đổi các quyết định trên cần ADR mới hoặc thay thế ADR hiện tại trước khi sửa schema/adapter.
