# Kế hoạch thiết kế và hiện thực tầng lưu trữ dữ liệu

> Đây là kế hoạch triển khai tầng lưu trữ, được xây dựng dựa trên ba tài liệu đặc tả nguồn `architect.md`, `project_requirements.md`, `usecase_detail.md` và phối hợp với `backend_implementation_plan.md`. Mỗi task bên dưới là một đơn vị triển khai, review, kiểm thử và commit độc lập. Không chuyển sang task kế tiếp khi task hiện tại chưa được người thực hiện review và chấp thuận. Các roadmap bên ngoài thư mục `files/` không phải nguồn yêu cầu và không được ghi đè kế hoạch chính thức này.

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
- Case có đúng một Operator sở hữu, không gắn khu vực và có trạng thái `OPEN` (Đang xử lý) hoặc `CLOSED` (Hoàn thành); `closed_at` chỉ có giá trị khi `CLOSED`.
- Tài khoản/camera ngừng hoạt động không làm mất dữ liệu lịch sử được Case tham chiếu; track của camera ngừng vận hành được giữ nguyên nhưng tạm ẩn khỏi tìm kiếm cho đến khi camera vận hành trở lại.
- Track chỉ được tìm kiếm khi metadata, full frame và vector đã được ghi hoàn chỉnh.

## 2. Nguồn yêu cầu và thứ tự ưu tiên

Ba tài liệu đặc tả nguồn (thẩm quyền cao nhất):

1. `files/architect.md` quy định kiến trúc chung và quyết định kỹ thuật chính thức.
2. `files/project_requirements.md` mô tả phạm vi nghiệp vụ.
3. `files/usecase_detail.md` mô tả luồng chính, ngoại lệ và quyền của 15 use case.

Kế hoạch thực thi dựa trên tài liệu nguồn: `files/backend_implementation_plan.md`, tài liệu này và `files/ai_worker_implementation_plan.md`.

Nếu có mâu thuẫn, không lấy roadmap hoặc code hiện tại làm yêu cầu. Tài liệu nguồn được ưu tiên; kế hoạch phải được sửa cho khớp trước khi triển khai. Nếu chính các tài liệu nguồn mâu thuẫn nhau, hỏi người thực hiện để chốt rồi cập nhật đồng bộ.

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
```

Cấu trúc cuối cùng có thể được tinh chỉnh ở STO-00 nhưng phải tiếp tục giữ ranh giới giữa domain, adapter lưu trữ và service điều phối.

## 5. Quy trình thực hiện một task

Mỗi task tuân theo cùng một vòng lặp:


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
| STO-05 | Schema PostgreSQL cho AI config, job và PersonTrack | STO-04 | DONE | `54f80d1` |
| STO-06 | Schema PostgreSQL cho Case, CaseResult và AuditLog | STO-05 | DONE | `91e073c` |
| STO-07 | Ràng buộc, index, seed và kiểm thử migration | STO-06 | DONE | `91e073c` |
| STO-08 | Repository và transaction cho PostgreSQL | STO-07 | DONE | `391acbb` |
| STO-09 | Adapter lưu full frame trên MinIO | STO-03 | DONE | `391acbb` |
| STO-10 | Collection và adapter vector trên Milvus | STO-03 | DONE | `391acbb` |
| STO-11 | Điều phối ghi track xuyên ba kho dữ liệu | STO-08, STO-09, STO-10 | DONE | `fe441fa` |
| STO-12 | Retry, reconciliation và xử lý dữ liệu dở dang | STO-11 | DONE | `8f0dd4f` |
| STO-13 | Truy vấn vector có lọc và kiểm tra quyền | STO-11 | DONE | `8f0dd4f` |
| STO-14 | Đọc ảnh, crop động và kiểm tra quyền truy cập | STO-11 | DONE | `8f0dd4f` |
| STO-15 | Lưu CaseResult và thống kê Viewer | STO-08, STO-14 | DONE | `22f5f51`, `183c4d0` (trạng thái Case) |
| STO-16 | Audit log và trạng thái vận hành lưu trữ | STO-08, STO-12 | DONE | `22f5f51` |
| STO-17 | Kiểm thử tích hợp và E2E toàn luồng | STO-13 đến STO-16 | DONE | `a99d48a` |
| STO-18 | Đo hiệu năng, tài nguyên và dung lượng | STO-17 | DONE | `a99d48a` |
| STO-19 | Backup, restore, bảo mật và runbook | STO-18 | DONE | `a99d48a` |

## 7. Chi tiết từng task

### STO-00 — Khởi tạo skeleton và bộ lệnh kiểm thử

**Mục tiêu:** tạo nền tảng tối thiểu để các task sau có cùng cấu trúc và cách chạy.

**Phạm vi thực hiện:**

- Tạo cấu trúc `backend`, `infra`, `scripts` (thư mục `docs/storage` tạo ở bước này đã gỡ khỏi repo ngày 2026-09-28; nội dung còn hiệu lực nằm trong code, `backend/README.md` và tài liệu này).
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

- `cases`: title, note, `owner_user_id`, timestamp; không có `area_id`. (Bản đầu không có `status`; cột `status`/`closed_at` được thêm sau bằng migration `20260927_0013`, xem mục STO-15.)
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

**Tiêu chí chấp nhận:** không có tình huống PostgreSQL báo `READY` nhưng object/vector bắt buộc chưa tồn tại; retry không nhân bản dữ liệu.

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
- Khi loại hit stale làm kết quả ít hơn `top_k`, truy vấn bù Milvus có giới hạn (over-fetch) để trả đủ `top_k` track hợp lệ nếu phạm vi còn dữ liệu (UC-09: trả tối đa `top_k` kết quả điểm cao nhất trong phạm vi hợp lệ).
- Trả Matching Score trong DTO response; không persist score.

**Kiểm thử:**

- Operator A không thể nhận track area B dù gửi camera ID trực tiếp.
- Filter xảy ra trước top-k, không phải lấy top-k toàn cục rồi mới bỏ kết quả.
- `top_k` ngoài tập cho phép bị từ chối.
- Track của camera đang ngừng vận hành không được trả về và camera đó không dùng được làm bộ lọc; khi camera vận hành trở lại thì track cũ được trả về bình thường.
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
- Dashboard đếm số row `CaseResult`, bao gồm các mục lặp cùng track, và số Case theo trạng thái.
- Trạng thái Case (bổ sung 2026-09-27, migration `20260927_0013_case_status.py`): enum PostgreSQL `case_status` (`OPEN`, `CLOSED`); cột `cases.status` `NOT NULL DEFAULT 'OPEN'` (Case có sẵn được backfill `OPEN`); cột `cases.closed_at timestamptz NULL`; ràng buộc `ck_cases_closed_at_matches_status`: `(status = 'CLOSED') = (closed_at IS NOT NULL)`; chỉ mục `ix_cases_status` cho lọc `?status=` và đếm dashboard. Downgrade xóa chỉ mục, ràng buộc, hai cột và kiểu enum. Khóa nội dung Case `CLOSED` (`409 case_closed`) nằm ở service, không dùng trigger.

**Kiểm thử:** duplicate save, owner spoofing, thêm vào Case người khác, đổi area sau khi tạo Case, Viewer read-only, dashboard count, xóa một duplicate và migration `0013` (backfill `OPEN`, ràng buộc `status`/`closed_at`, enum lạ bị từ chối, downgrade/upgrade khứ hồi: `test_case_status_migration_backfills_open_and_round_trips`).

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
- File quan trọng: `backend/src/person_search/storage/`, `backend/tests/unit/test_storage_skeleton.py`, `scripts/check.ps1`, `scripts/check.sh`, `infra/README.md`.
- Test đã chạy: PowerShell `scripts/check.ps1`; Git Bash `scripts/check.sh`; pytest với coverage; `git diff --check`.
- Kết quả: 23 test đạt; coverage 79%; Ruff sạch; toàn bộ source compile thành công; package storage import được khi PostgreSQL/Milvus/MinIO không chạy.
- Điểm cần người thực hiện review: tên các namespace, vị trí migrations, hai script kiểm tra và việc chưa thêm dependency storage trong STO-00.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chuyển sang STO-01 sau khi commit.
- Commit SHA: `cc440d4`.

### 2026-09-25 — STO-01

- Trạng thái: `DONE`.
- Thay đổi chính: chấp thuận ADR-0001 cho vai trò ba kho, UUIDv4, UTC/source timeline, bbox pixel, state machine, soft-delete, naming MinIO/Milvus, RaSa vector profile và write ordering; bổ sung contract executable giữa AI worker và storage service.
- File quan trọng: `backend/src/person_search/storage/contracts.py`, `backend/tests/unit/test_storage_contracts.py`.
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
- File quan trọng: `backend/alembic.ini`, `backend/migrations/versions/20260925_0001_area_user_camera.py`, `backend/src/person_search/storage/postgres/models/`, `backend/tests/integration/test_identity_schema.py`.
- Test đã chạy: `scripts/check.ps1`; 81 unit test; migration integration trên database dùng một lần; `downgrade base → upgrade head → alembic check → constraint tests → downgrade base`; Ruff; compileall; branch coverage; `git diff --check`.
- Kết quả: 81 unit test đạt; migration integration đạt; Alembic không phát hiện schema drift; Operator thiếu area và Admin có area bị từ chối; Camera thiếu area hoặc RTSP nhúng credential bị từ chối; đổi Camera area bị chặn ở ORM lẫn raw SQL; đổi Area code bị chặn; xóa Area đang được User/Camera tham chiếu bị FK `RESTRICT` chặn; inactive row vẫn giữ area FK; downgrade xóa sạch ba bảng/type; unit branch coverage tổng 89%.
- Điểm cần người thực hiện review: enum/status, quy tắc uppercase và bất biến của code, role–area constraint, việc chỉ lưu `rtsp_secret_ref`, trigger PostgreSQL, tên migration và giới hạn STO-04 chưa có repository nghiệp vụ đầy đủ.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và yêu cầu chuyển sang STO-05.
- Commit SHA: `ba19a77`.

### 2026-09-25 — STO-05

- Trạng thái: `DONE`.
- Thay đổi chính: thêm model và migration cho phiên bản cấu hình AI, processing job, PersonTrack và transactional outbox; bảo vệ bbox/timeline/progress bằng constraint; khóa state machine track ở cả ORM và PostgreSQL; chỉ cho phép `READY` khi MinIO artifact và vector index đã được xác nhận; giữ đầy đủ lineage camera/area/job/config/encoder và không lưu Matching Score.
- File quan trọng: `backend/migrations/versions/20260925_0002_processing_tracks.py`, `backend/src/person_search/storage/postgres/models/ai_config.py`, `processing_job.py`, `person_track.py`, `outbox.py`, `backend/tests/integration/test_processing_schema.py`.
- Test đã chạy: Ruff; 85 unit test; migration integration trên database dùng một lần; `downgrade base → upgrade head → alembic check → constraint/state-transition tests → downgrade 0001 → downgrade base`.
- Kết quả: unit và integration đều đạt; Alembic không phát hiện schema drift; PostgreSQL từ chối sampling interval không dương, bbox vượt frame, track khởi tạo ở `READY`, `READY` thiếu artifact và chuyển ngược `READY → FAILED`; rollback giữ schema STO-04 rồi xóa sạch về base.
- Điểm cần người thực hiện review: bộ field lineage, quy tắc một AI config `ACTIVE`, state machine `PENDING → READY/FAILED`, retry `FAILED → PENDING`, `READY` là trạng thái cuối, payload JSONB và unique `(track_id, event_type)` của outbox.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận, commit và yêu cầu triển khai STO-06 cùng STO-07.
- Commit SHA: `54f80d1`.

### 2026-09-25 — STO-06

- Trạng thái: `DONE`.
- Thay đổi chính: thêm Case, CaseResult snapshot và AuditLog; owner Case được suy ra từ Operator đăng nhập và được trigger PostgreSQL kiểm tra; cho phép lưu cùng track nhiều lần; snapshot bất biến; audit append-only; không có status/area/Matching Score trong Case.
- File quan trọng: `backend/migrations/versions/20260925_0003_cases_and_audit.py`, `backend/src/person_search/storage/postgres/models/case.py`, `case_result.py`, `audit_log.py`, `backend/src/person_search/services/case_policy.py`.
- Test đã chạy: unit policy/schema; integration PostgreSQL cho owner role, duplicate result, delete độc lập, khóa Operator, snapshot và audit append-only.
- Kết quả: test đạt; Viewer/Admin bị từ chối làm owner; khóa Operator không làm mất Case; xóa một CaseResult không xóa result còn lại hoặc PersonTrack.
- Điểm cần người thực hiện review: CaseResult cascade theo Case nhưng `RESTRICT` về PersonTrack; actor audit được `SET NULL`; audit và snapshot là bất biến.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và commit cùng STO-07.
- Commit SHA: `91e073c`.

### 2026-09-25 — STO-07

- Trạng thái: `DONE`.
- Thay đổi chính: thêm index theo camera active, job status và timeline/status track; partial index cho track `READY`; seed Area development idempotent không chứa secret; xuất ER diagram và data dictionary; kiểm thử migration trên database đã có dữ liệu.
- File quan trọng: `backend/migrations/versions/20260925_0004_schema_hardening.py`, `backend/src/person_search/storage/postgres/seed.py`, `backend/tests/integration/test_case_and_hardening_schema.py`.
- Test đã chạy: seed hai lần; migration `base → 0003` với dữ liệu → `head`; `alembic check`; kiểm tra index; `EXPLAIN`; downgrade `0003` rồi upgrade lại `head`; cuối cùng downgrade base.
- Kết quả: test đạt; lần seed thứ hai thêm 0 row; database có dữ liệu nâng cấp thành công; query READY theo camera dùng partial index; upgrade/downgrade lặp lại không lệch schema.
- Điểm cần người thực hiện review: danh sách Area mẫu, partial index `READY`, phạm vi seed chủ động ngoài production migration và sơ đồ ER/data dictionary.
- Quyết định/chỉnh sửa sau review: người thực hiện đã chấp thuận và commit cùng STO-06.
- Commit SHA: `91e073c`.

### 2026-09-25 — STO-08

- Trạng thái: `DONE`.
- Thay đổi chính: repository cho toàn bộ model, actor-scoped query, cursor pagination, Unit of Work commit/rollback, mapping lỗi constraint và optimistic update bằng `updated_at`.
- Test đã chạy: unit với mocked session; integration PostgreSQL thật cho commit, rollback, duplicate mapping, pagination và concurrent update.
- Kết quả: test đạt; transaction lỗi không để lại row nửa chừng và writer dùng dữ liệu cũ bị từ chối.
- Điểm cần review: API repository registry, giới hạn page 100 và chiến lược optimistic concurrency.
- Commit SHA: —.

### 2026-09-25 — STO-09

- Trạng thái: `DONE`.
- Thay đổi chính: adapter put/head/get/delete frame; key ổn định; kiểm tra MIME, decode, dimension, size và SHA-256; put idempotent và conflict khi checksum khác; không phát URL public.
- Test đã chạy: fake MinIO cho idempotency/corruption/conflict; integration MinIO thật cho round-trip và anonymous access.
- Kết quả: unit và integration đạt; checksum giữ nguyên và anonymous HTTP trả 403.
- Điểm cần review: hỗ trợ JPEG/PNG, giới hạn mặc định 20 MiB và metadata tối thiểu.
- Commit SHA: —.

### 2026-09-25 — STO-10

- Trạng thái: `DONE`.
- Thay đổi chính: collection versioned, alias, HNSW/IP index, vector validation, typed filter builder, upsert/get/delete/search và DTO score tạm thời.
- Test đã chạy: unit dimension/NaN/normalization/filter; integration Milvus thật cho ensure idempotent, upsert, filter trước top-k, get và delete.
- Kết quả: unit và integration đạt; area filter loại track ngoài phạm vi dù vector giống hệt; collection test được dọn sạch.
- Điểm cần review: HNSW `M=16`, `efConstruction=128`, search `ef=64`, tập top-k và collection/alias naming.
- Commit SHA: —.

### 2026-09-25 — STO-11

- Trạng thái: `DONE`.
- Thay đổi chính: `TrackIngestionService.ingest_track` với register `PENDING` + outbox trong một transaction, upload MinIO, upsert Milvus, publish `READY`; idempotency theo `track_id` và conflict khi identity khác; phân loại lỗi retryable/non-retryable, exponential backoff, `FAILED`/`DEAD` khi vượt giới hạn; `PersonTrackRepository.get_for_update/ready_ids`, `StorageOutboxRepository.get_for_track`, `UnitOfWork.flush`; object key MinIO đổi sang prefix `tracks/v1` theo contract.
- Quyết định: đường đọc lọc hit Milvus qua `ready_ids` của PostgreSQL (phương án a); embedding lưu trong outbox payload để STO-12 retry bước Milvus, frame bytes không lưu.
- Test đã chạy: toàn bộ unit suite, Ruff, compile và integration `tests/integration/test_track_ingestion_flow.py` trên PostgreSQL/MinIO/Milvus thật.
- Kết quả: 162 unit test đạt; integration ingest xuyên ba kho đạt sau khi bổ sung strong consistency và read-back Milvus trước khi publish `READY`; Ruff sạch; compile thành công.
- Điểm cần review: danh sách lỗi non-retryable, `RetryPolicy` mặc định, giữ embedding trong outbox sau khi `COMPLETED`.
- Commit SHA: —.

### 2026-09-25 — STO-12

- Trạng thái: `DONE`.
- Thay đổi chính: `OutboxRetryWorker` claim event đến hạn bằng `FOR UPDATE SKIP LOCKED` và thu hồi event `PROCESSING` quá `lock_timeout`; `TrackIngestionService.resume` kiểm tra frame MinIO, upsert vector từ embedding trong outbox rồi publish; `requeue_failed` đưa `FAILED → PENDING` kèm audit; `StorageReconciler` báo track treo, object/vector thiếu, checksum sai, orphan object/vector theo batch, mặc định dry-run; chế độ `--delete-orphans` kiểm tra lại PostgreSQL/CaseResult trước khi xóa và ghi audit; CLI `person-search-storage`.
- Quyết định: track `READY` thiếu object/vector chỉ được báo cáo, không hạ trạng thái (vì `READY` không được chuyển ngược); frame thiếu là lỗi retryable nhưng worker không tự upload được.
- Test đã chạy: toàn bộ unit suite, Ruff, compile và integration `tests/integration/test_storage_read_paths.py` trên PostgreSQL/MinIO/Milvus thật.
- Kết quả: 162 unit test đạt; retry, dead-letter, requeue, reconciliation dry-run và xóa orphan an toàn đều đạt; database/object/collection test đã được dọn sạch.
- Điểm cần review: `lock_timeout` 5 phút, `stale_after` 30 phút, giới hạn `max_items` 10.000, exit code CLI.
- Commit SHA: —.

### 2026-09-25 — STO-13

- Trạng thái: `DONE`.
- Thay đổi chính: `TrackSearchService.search` lấy area từ PostgreSQL, từ chối camera ngoài area trước khi gọi Milvus, gửi filter area/camera/time vào Milvus trước top-k, hydrate và recheck `READY`/area/camera/time ở PostgreSQL, bỏ hit stale kèm metric; `VectorFilter` hỗ trợ nhiều camera.
- Quyết định: track của camera `INACTIVE`/`RETIRED` vẫn tìm được nếu thuộc area hiện tại; Operator không `ACTIVE` không được tìm kiếm.
- Test đã chạy: toàn bộ unit suite, Ruff, compile và integration search trên PostgreSQL/Milvus thật.
- Kết quả: 162 unit test đạt; filter Area được áp dụng trước top-k, camera ngoài quyền bị từ chối và PostgreSQL recheck chỉ giữ track `READY`.
- Điểm cần review: policy camera ngừng hoạt động, việc trả ít hơn `top_k` khi có hit stale thay vì truy vấn bù.
- Đính chính 2026-09-27 theo quyết định của người thực hiện: thay quyết định trên — track của camera `INACTIVE`/`RETIRED` được giữ nhưng **không** tìm được cho đến khi camera vận hành trở lại; filter Milvus giới hạn vào camera `ACTIVE` của area trước top-k. Bổ sung truy vấn bù khi hit stale làm kết quả ít hơn `top_k` (tối đa 3 vòng, limit `top_k`, `2×`, `4×`). Code: `services/track_search.py`, `track_imagery.py`, `cases.py`, `CameraRepository.active_ids_in_area`; unit test đạt.
- Commit SHA: —.

### 2026-09-25 — STO-14

- Trạng thái: `DONE`.
- Thay đổi chính: `TrackImageService` với hai context `search_result_image` (Operator, track `READY` trong area hiện tại) và `case_result_image` (owner Operator hoặc Viewer, theo `case_result_id`); crop động có clamp/padding, full frame có viền bbox, downscale, giới hạn kích thước, `Cache-Control: private, no-store`; lỗi ảnh có `reason` rõ ràng.
- Quyết định: 403 cho sai vai trò/tài khoản không `ACTIVE`, 404 cho đối tượng không tồn tại hoặc không thuộc quyền; ảnh Case tra theo `case_result_id`; ảnh có kích thước khác metadata track được coi là hỏng.
- Test đã chạy: toàn bộ unit suite, Ruff, compile và integration imagery trên PostgreSQL/MinIO thật.
- Kết quả: 162 unit test đạt; crop/full frame, quyền Operator/Viewer, ảnh Case và cleanup object test đều đạt.
- Điểm cần review: màu/độ dày viền bbox, `max_edge` 1920, giới hạn 5 MiB, padding mặc định 0.
- Commit SHA: —.

### 2026-09-25 — STO-15

- Trạng thái: `DONE`.
- Thay đổi chính: `CaseService` tạo/sửa Case, thêm/xóa `CaseResult`, list/detail, dashboard Viewer; owner lấy từ actor đọc lại ở PostgreSQL; lưu track chỉ khi track `READY` thuộc area hiện tại; snapshot camera/area/thời gian phía server; không deduplicate; optimistic check bằng `expected_updated_at`; cursor keyset; audit `case.*` thành công trong cùng transaction và audit thất bại khi bị từ chối.
- Quyết định: Case người khác trả 404, sai vai trò trả 403; thêm/xóa mục cập nhật `cases.updated_at`; list sắp xếp theo `created_at`, dashboard theo `updated_at`; title tối đa 200, note tối đa 5000 ký tự.
- Test đã chạy: toàn bộ unit suite (194 test đạt), Ruff, compile và integration service trên PostgreSQL thật.
- Kết quả: 19 unit test mới đạt; integration xác nhận duplicate CaseResult, Viewer read-only, đổi Area vẫn xem Case cũ và dashboard đếm đúng từng row.
- Điểm cần review: giới hạn độ dài note, quy tắc 403/404, audit không ghi nội dung title/note.
- Commit SHA: —.

### 2026-09-25 — STO-16

- Trạng thái: `DONE`.
- Thay đổi chính: catalog `AuditEvent`, `redact_metadata`, `record_audit`/`AuditRecorder`, `AuditLogService` cho Admin với filter và cursor; audit `storage.track_failed`; hai audit storage cũ chuyển sang catalog; `StorageMetrics` theo component và thời gian ingestion; `StorageStatusService` tổng hợp track/outbox/health/cảnh báo.
- Quyết định: metric in-memory theo tiến trình; search không tạo audit; audit thất bại không làm hỏng thao tác chính.
- Test đã chạy: toàn bộ unit suite (194 test đạt), Ruff, compile và integration service trên PostgreSQL thật.
- Kết quả: 13 unit test mới đạt; integration xác nhận audit SUCCESS/FAILURE, filter event, metadata chuẩn hóa, quyền Admin, track/outbox counts và cảnh báo component health.
- Điểm cần review: danh sách key bị redact, ngưỡng vector 16 phần tử, metric in-memory có đủ cho demo không.
- Commit SHA: —.

### 2026-09-25 — STO-17

- Trạng thái: `DONE`.
- Thay đổi chính: `tests/e2e/test_storage_workflow.py` chạy đủ 9 bước bắt buộc trên stack thật (seed 2 area, ingest `READY`, search theo area, crop/full frame, Case lưu trùng track, đổi area, Viewer/dashboard, MinIO và Milvus unavailable rồi retry) cùng bước sửa Case hai lần, reconcile và status Admin; fixture `storage_stack` làm sạch schema, dùng collection/alias riêng và tự dọn; mỗi bước báo lỗi kèm tên component.
- Sửa kèm: `CaseService.update_case` đọc lại `updated_at` sau flush vì trigger `set_row_updated_at` ghi đè giá trị do service đặt, trước đó lần sửa thứ hai dùng `updated_at` trả về sẽ luôn bị `ConcurrentUpdateError` trên PostgreSQL thật.
- Test đã chạy: unit suite, Ruff, compile và E2E trên PostgreSQL, MinIO, Milvus thật với database tạm biệt lập.
- Kết quả: E2E đạt toàn bộ workflow, gồm phân quyền theo area, ảnh, Case/Viewer, fault injection MinIO/Milvus, retry, reconciliation và trạng thái Admin.
- Commit SHA: —.

### 2026-09-25 — STO-18

- Trạng thái: `DONE`.
- Thay đổi chính: `backend/tools/storage_benchmark.py` đo throughput ingestion, p50/p95/p99 search (Milvus thuần và qua service), recall@k theo `ef`, latency crop/full frame, dung lượng mỗi track, stats Docker; dữ liệu tổng hợp 7 camera/2 area; tự dọn dữ liệu.
- Sửa kèm: mã Area/Camera benchmark luôn được chuẩn hóa uppercase để thỏa constraint PostgreSQL; có unit test hồi quy.
- Test đã chạy: unit test cho percentile, vector và mã seed; smoke benchmark thật với 3 track 256 chiều, đọc ảnh và Docker stats.
- Kết quả: 3/3 track `READY`, recall@4 = 1,0, crop/full frame thành công và thu được CPU/RAM của bốn container. Đây là smoke baseline; các mốc 1.000/5.000/10.000 track vẫn cần chạy trên máy demo trước release.
- Commit SHA: —.

### 2026-09-25 — STO-19

- Trạng thái: `DONE`.
- Thay đổi chính: `backend/tools/storage_backup.py` (`backup`/`verify`/`restore`) với `pg_dump -Fc`, export frame theo PostgreSQL kèm kiểm tra SHA-256, manifest có checksum/phiên bản/thời gian; restore theo thứ tự PostgreSQL → MinIO (kèm metadata) → reindex Milvus → reconcile; `StorageReindexer` và lệnh `person-search-storage reindex`; `backups/` vào `.gitignore` (các lệnh vận hành nay ở `backend/README.md`).
- Quyết định: Milvus không copy mà dựng lại từ embedding trong outbox (đã nằm trong dump PostgreSQL); không dùng `mc mirror` vì mất metadata `sha256`.
- Sửa kèm: `pg_dump`, `psql` và `pg_restore` lấy đúng user/database từ DSN thay vì luôn thao tác database mặc định của Compose; có unit test hồi quy.
- Test đã chạy: unit test cho reindexer, verify manifest, chặn path traversal, bắt buộc `--yes`; restore drill trên database tạm sau khi xóa schema và 3 frame.
- Kết quả: backup/verify đạt; khôi phục 3 track và upload lại 3 frame; reindex 3/3; không thiếu object/vector và không sai checksum; RTO tổng thử nghiệm 5,522 giây.
- Commit SHA: —.

### 2026-09-27 — STO-15 (bổ sung trạng thái Case)

- Trạng thái: `DONE`.
- Thay đổi chính: migration `20260927_0013_case_status.py` thêm enum `case_status`, cột `cases.status` (mặc định `OPEN`), `cases.closed_at`, ràng buộc `ck_cases_closed_at_matches_status` và chỉ mục `ix_cases_status`; model `Case`/`CaseStatus`; dashboard đếm `open_cases`/`closed_cases`.
- Test đã chạy (2026-09-28, R3): integration migration/schema 7 passed trên database dùng một lần `person_search_citest`, gồm test mới cho `0013`; `alembic check` không phát hiện sai lệch model.
- Commit SHA: `183c4d0` (migration, model); test migration chưa commit.

### 2026-09-28 — STO-19 (khôi phục với dữ liệu demo thật)

- Trạng thái: `DONE`.
- Phát hiện: diễn tập khôi phục 1.555 track mất 1.485 s, trong đó reindex Milvus 1.468 s (một upsert
  và một truy vấn xác minh cho mỗi vector), 1 vector `DEADLINE_EXCEEDED`.
- Thay đổi chính: `MilvusPersonTrackIndex.upsert_many`/`existing_ids` và `VectorRecord`
  (`storage/milvus/vectors.py`); `StorageReindexer` ghi và xác minh theo lô 200, lô lỗi thì thử lại
  từng vector (`services/storage_maintenance.py`); lệnh `person-search-storage reindex` dùng chung.
- Test đã chạy: unit 711 passed (+3 test reindex theo lô, thử lại, unverified); diễn tập lại sau khi
  xóa 10 object MinIO: tổng 28,8 s (reindex 8,8 s), upload lại 10/10 ảnh, 1.555/1.555 vector,
  reconcile sạch.
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

ADR-0001 gốc nằm trong thư mục `docs/` đã gỡ khỏi repo ngày 2026-09-28 (xem lịch sử Git, commit `222c0ad`); các quyết định còn hiệu lực là danh sách trên. Thay đổi các quyết định này phải cập nhật mục này và ba tài liệu nguồn trước khi sửa schema/adapter.
