# Kế hoạch thiết kế và hiện thực Backend

> Tài liệu làm việc cho Flask API và các tiến trình backend của ứng dụng tìm kiếm người qua camera. Mỗi task là một đơn vị triển khai, kiểm thử, review và commit độc lập. Sau khi hoàn thành một task, dừng để người thực hiện review; chỉ commit và chuyển task khi test đạt và review được chấp thuận.

## 1. Mục tiêu Backend

Backend cung cấp API và các service nghiệp vụ cho ba vai trò:

- **Admin:** xác thực, quản lý tài khoản, camera, xử lý AI, cấu hình Detector/Tracker, trạng thái hệ thống, chẩn đoán AI và audit log.
- **Operator:** tìm kiếm người trong đúng khu vực được gán, xem kết quả và quản lý Case của chính mình.
- **Viewer:** xem dashboard, toàn bộ Case và các kết quả đã lưu ở chế độ chỉ đọc.

Backend đồng thời điều phối các thành phần kỹ thuật:

- Flask HTTP API.
- PostgreSQL, Milvus và MinIO thông qua tầng lưu trữ được lập kế hoạch trong `storage_database_implementation_plan.md`.
- Background worker xử lý job video/RTSP ngoài vòng đời request.
- Gateway tới Detector, Tracker và RaSa Image/Text Encoder.
- Kiểm tra quyền cho mọi dữ liệu, bao gồm endpoint trả crop/full frame.
- Audit, health check, metric, error handling và quy trình vận hành.

## 2. Ranh giới trách nhiệm

### Backend sẽ xây dựng

- API versioned, validation, serialization và error response thống nhất.
- Xác thực phiên đăng nhập, đăng xuất, kiểm tra trạng thái tài khoản và phân quyền.
- Service nghiệp vụ cho toàn bộ UC-01 đến UC-15.
- API tạo job xử lý video, hàng đợi tuần tự và giao tiếp với AI pipeline.
- Điều phối tìm kiếm ảnh/văn bản/thuộc tính, kiểm tra khu vực, gọi encoder và vector search.
- API Case, Viewer dashboard, audit log, system status và diagnostics.
- Streaming ảnh/crop qua backend sau khi kiểm tra quyền.
- Test unit, integration, authorization, E2E, performance và tài liệu vận hành.

### Backend không tự nhận trách nhiệm trong kế hoạch này

- Huấn luyện hoặc fine-tune Detector, Tracker hay RaSa.
- Quyết định chất lượng checkpoint AI mà chưa có phép đo.
- Giao diện React/Vite.
- Xử lý đồng thời bảy luồng AI trong buổi demo.
- Lưu person crop thành object bền vững.
- Dùng Matching Score làm kết luận danh tính hoặc ngưỡng tự động loại kết quả.

Việc tích hợp model sẽ thông qua interface rõ ràng. Mã suy luận cụ thể có thể nằm trong package AI riêng nhưng worker/backend phải kiểm soát job, timeout, trạng thái, persistence và lỗi.

## 3. Nguồn yêu cầu và quy tắc ưu tiên

1. `files/architect.md` là nguồn quyết định mới nhất.
2. `files/usecase_detail.md` mô tả luồng chính, ngoại lệ và hậu điều kiện của UC-01 đến UC-15.
3. `files/project_requirements.md` mô tả phạm vi nghiệp vụ tổng quát.
4. `files/storage_database_implementation_plan.md` quy định cách backend tương tác với ba kho dữ liệu.

Các quyết định bắt buộc phải được giữ xuyên suốt backend:

- `top_k` chỉ nhận một trong `{4, 8, 12, 16}`.
- Matching Score chỉ xuất hiện trong response của lượt tìm kiếm, không lưu vào Case.
- Mỗi lần thêm kết quả tạo một `CaseResult` mới; cho phép lặp cùng `track_id`.
- Operator chỉ tìm kiếm camera/track thuộc khu vực hiện tại do backend lấy từ tài khoản.
- Operator đổi khu vực vẫn xem và quản lý Case cũ do mình sở hữu.
- Case không có trạng thái, không gắn khu vực và có đúng một Operator owner.
- Viewer xem mọi Case nhưng không được tìm kiếm hoặc sửa dữ liệu.
- Admin quản trị kỹ thuật, không mặc nhiên có quyền tìm kiếm hoặc xem mọi Case.
- Ảnh kết quả được tạo động từ full frame và bbox; MinIO không public.
- Demo nhận file video và có thể xử lý tuần tự; RTSP là đường thử nghiệm tại nhà.
- Detector/Tracker là cấu hình chung toàn hệ thống; Image/Text Encoder cố định trong phiên bản đầu.

## 4. Kiến trúc Backend dự kiến

```text
Browser / Frontend
        |
        v
Flask API
  ├── Auth + session
  ├── Request validation / response DTO
  ├── Authorization policies
  ├── Admin services
  ├── Search services
  ├── Case / Viewer services
  └── Media delivery
        |
        ├── PostgreSQL repositories
        ├── Milvus vector adapter
        ├── MinIO frame adapter
        └── Job queue / worker boundary
                       |
                       v
        Video source → Sampling → Detector → Tracker → RaSa
```

Nguyên tắc:

- Route chỉ làm HTTP parsing, gọi service và map response; không chứa truy vấn ORM hoặc logic quyền phức tạp.
- Service chứa use case và transaction boundary.
- Policy nhận actor + resource/context và trả quyết định quyền rõ ràng.
- Repository/adapter chịu trách nhiệm truy cập storage; không trả ORM object trực tiếp ra API.
- AI inference dài hạn không chạy trong request Flask.
- DTO request/response tách khỏi SQLAlchemy model.

## 5. Cấu trúc thư mục đích dự kiến

```text
backend/
  src/person_search/
    app.py
    config.py
    api/
      errors.py
      middleware.py
      v1/
        auth.py
        admin_users.py
        admin_cameras.py
        admin_ai.py
        admin_status.py
        searches.py
        cases.py
        viewer.py
        media.py
    auth/
      sessions.py
      passwords.py
      decorators.py
    policies/
    domain/
    services/
    storage/
    ai/
      contracts.py
      query_encoder.py
      pipeline.py
    workers/
      processing_worker.py
      reconciliation_worker.py
  tests/
    unit/
    contract/
    integration/
    security/
    e2e/
```

Cấu trúc cuối cùng được chốt ở BE-00/BE-01. Không tạo module chỉ để khớp sơ đồ nếu chưa có trách nhiệm thực tế.

## 6. Quy trình thực hiện một task

> Thư mục làm việc chưa có metadata Git tại thời điểm lập kế hoạch. Trước commit đầu tiên phải xác nhận đúng repository và chỉ khởi tạo Git hoặc chuyển repository khi người thực hiện yêu cầu.

1. Chọn đúng một task có dependency đã hoàn thành.
2. Chuyển task sang `IN_PROGRESS` và chỉ sửa phạm vi task đó.
3. Bổ sung/cập nhật test cùng lúc với code.
4. Chạy test bắt buộc và kiểm tra diff.
5. Chuyển sang `READY_FOR_REVIEW`, ghi nhật ký và dừng để người thực hiện review.
6. Sửa theo review trên cùng task, chạy lại test.
7. Khi người thực hiện xác nhận, tạo một commit riêng và ghi SHA.
8. Chỉ sau đó chuyển task sang `DONE` và bắt đầu task tiếp theo.

Trạng thái hợp lệ: `TODO`, `IN_PROGRESS`, `READY_FOR_REVIEW`, `DONE`, `BLOCKED`.

### Definition of Done chung

- Hành vi mới có test phù hợp; test cũ vẫn đạt.
- API contract, status code và error code được cập nhật.
- Quyền được enforce ở backend, không dựa vào việc ẩn nút trên UI.
- Không log password, token, RTSP credential, raw image hoặc raw embedding.
- Không thực hiện I/O dài hoặc AI inference trực tiếp trong request nếu có thể đưa sang worker.
- Migration/schema liên quan đã hoàn tất theo task `STO-*` tương ứng.
- Không có secret, file video thật, frame thật hoặc volume local trong Git.
- Người thực hiện đã review trước khi commit.

## 7. Bảng theo dõi tổng thể

| Task | Nội dung | Dependency chính | Trạng thái | Commit |
| --- | --- | --- | --- | --- |
| BE-00 | Khởi tạo backend application skeleton | Không; dùng chung nền với STO-00 | DONE | `first commit` |
| BE-01 | Chốt API contract và quy ước HTTP | BE-00, STO-01 | TODO | — |
| BE-02 | Nền tảng password, session và CSRF | BE-01, STO-04 | READY_FOR_REVIEW | — |
| BE-03 | UC-01/UC-15: đăng nhập, phiên và đăng xuất | BE-02 | READY_FOR_REVIEW | — |
| BE-04 | Policy phân quyền tập trung | BE-03 | TODO | — |
| BE-05 | UC-02: quản lý Area tham chiếu và tài khoản | BE-04, STO-08 | READY_FOR_REVIEW | — |
| BE-06 | UC-03: quản lý camera và kiểm tra RTSP | BE-04, STO-08 | TODO | — |
| BE-07 | UC-05: registry và cấu hình Detector/Tracker | BE-04, STO-08 | TODO | — |
| BE-08 | UC-04: bật/tắt AI theo camera | BE-06, BE-07 | TODO | — |
| BE-09 | API upload video và quản lý processing job | BE-06, STO-05 | TODO | — |
| BE-10 | Background worker và cổng tích hợp AI pipeline | BE-07 đến BE-09, STO-11 | TODO | — |
| BE-11 | UC-06: trạng thái hệ thống và processing job | BE-08, BE-10 | TODO | — |
| BE-12 | UC-07: chẩn đoán Camera Pipeline/Search Components | BE-10 | TODO | — |
| BE-13 | UC-08: ghi và tra cứu audit log | BE-05 đến BE-12, STO-16 | TODO | — |
| BE-14 | Chuẩn bị truy vấn ảnh/văn bản/thuộc tính | BE-04, BE-10 | TODO | — |
| BE-15 | UC-09: tìm kiếm có lọc và phân quyền | BE-14, STO-13 | TODO | — |
| BE-16 | UC-10: trình bày kết quả và media có quyền | BE-15, STO-14 | TODO | — |
| BE-17 | UC-11: quản lý Case và CaseResult | BE-16, STO-15 | TODO | — |
| BE-18 | UC-12, UC-13, UC-14: Viewer dashboard và xem Case | BE-17 | TODO | — |
| BE-19 | Quy tắc lịch sử khi User/Camera thay đổi vòng đời | BE-05, BE-06, BE-17 | TODO | — |
| BE-20 | Idempotency, concurrency và error handling | BE-03 đến BE-19 | TODO | — |
| BE-21 | Hardening bảo mật API và upload | BE-20 | TODO | — |
| BE-22 | Logging, metric, tracing và readiness | BE-11, BE-20 | TODO | — |
| BE-23 | Test contract, integration, authorization và E2E | BE-03 đến BE-22, STO-17 | TODO | — |
| BE-24 | Đo hiệu năng và tài nguyên Backend | BE-23, STO-18 | TODO | — |
| BE-25 | Đóng gói, cấu hình triển khai và runbook | BE-24, STO-19 | TODO | — |

## 8. Bản đồ endpoint dự kiến

Tên và payload cuối cùng được khóa ở BE-01. Bảng này dùng để kiểm tra độ phủ, không phải contract đã hoàn tất.

| Nhóm | Endpoint dự kiến | Vai trò |
| --- | --- | --- |
| Auth | `POST /api/v1/auth/login` | Public |
| Auth | `POST /api/v1/auth/logout`, `GET /api/v1/auth/me` | Đã đăng nhập |
| Area | `GET /api/v1/areas` | Admin khi gán Operator; các use case được phép |
| User | `GET/POST /api/v1/admin/users` | Admin |
| User | `GET/PATCH/DELETE /api/v1/admin/users/{id}` | Admin |
| User | `POST /api/v1/admin/users/{id}/lock`, `/unlock` | Admin |
| Camera | `GET/POST /api/v1/admin/cameras` | Admin |
| Camera | `GET/PATCH/DELETE /api/v1/admin/cameras/{id}` | Admin |
| Camera | `POST /api/v1/admin/cameras/{id}/connection-tests` | Admin |
| AI | `PUT /api/v1/admin/cameras/{id}/ai-state` | Admin |
| AI config | `GET /api/v1/admin/ai/models`, `GET/PUT /api/v1/admin/ai/config` | Admin |
| Job | `POST /api/v1/admin/cameras/{id}/processing-jobs` | Admin |
| Job | `GET /api/v1/admin/processing-jobs`, `GET /{id}` | Admin |
| Status | `GET /api/v1/admin/system-status` | Admin |
| Diagnostic | `POST /api/v1/admin/diagnostics/camera-pipeline` | Admin |
| Diagnostic | `POST /api/v1/admin/diagnostics/search-components` | Admin |
| Audit | `GET /api/v1/admin/audit-logs` | Admin |
| Search | `POST /api/v1/searches/image` | Operator |
| Search | `POST /api/v1/searches/text` | Operator |
| Search | `POST /api/v1/searches/attributes` | Operator |
| Search media | `GET /api/v1/search-results/{track_id}/crop` | Operator có quyền hiện tại |
| Search media | `GET /api/v1/search-results/{track_id}/frame` | Operator có quyền hiện tại |
| Case | `GET/POST /api/v1/cases` | Operator; GET có semantics riêng cho Viewer nếu thống nhất |
| Case | `GET/PATCH /api/v1/cases/{id}` | Operator owner; Viewer chỉ GET |
| Case result | `POST /api/v1/cases/{id}/results` | Operator owner |
| Case result | `DELETE /api/v1/cases/{id}/results/{case_result_id}` | Operator owner |
| Case media | `GET /api/v1/cases/{id}/results/{case_result_id}/crop` | Operator owner hoặc Viewer |
| Case media | `GET /api/v1/cases/{id}/results/{case_result_id}/frame` | Operator owner hoặc Viewer |
| Viewer | `GET /api/v1/viewer/dashboard` | Viewer |
| Health | `GET /health/live`, `GET /health/ready` | Hạ tầng; response giới hạn thông tin |

## 9. Ma trận quyền mục tiêu

| Khả năng | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| Quản lý user/camera/AI/model | Có | Không | Không |
| Xem status/diagnostic/audit | Có | Không | Không |
| Tìm kiếm | Không mặc định | Trong area hiện tại | Không |
| Xem media của lượt tìm kiếm | Không mặc định | Trong area hiện tại | Không |
| Tạo/sửa Case | Không | Chỉ Case sở hữu | Không |
| Xem Case | Không mặc định | Chỉ Case sở hữu | Tất cả, chỉ đọc |
| Xem media trong Case | Không mặc định | Case sở hữu | Tất cả Case |
| Dashboard Viewer | Không | Không | Có |

Không xây dựng “superuser bypass” ẩn. Nếu tương lai cần một vai trò mới, phải bổ sung policy/test tường minh.

## 10. Chi tiết từng task

### BE-00 — Khởi tạo backend application skeleton

**Mục tiêu:** tạo Flask application có cấu trúc module, dependency injection và test smoke nhất quán với STO-00.

**Phạm vi:**

- Application factory theo environment.
- Blueprint `/api/v1`, health blueprint và error handler tối thiểu.
- Cơ chế inject repository, storage client, clock và AI gateway để test không cần service thật.
- CLI entrypoint cho web app và worker placeholder.
- Cấu hình pytest cho route/service test.
- Không khởi tạo kết nối storage tại import time.

**Không làm:** endpoint nghiệp vụ, authentication thật, ORM model hoặc AI inference.

**Kiểm thử:** tạo nhiều app instance với config khác nhau; request test client tới liveness; import package không cần PostgreSQL/Milvus/MinIO đang chạy.

**Tiêu chí chấp nhận:** app khởi động được, route prefix ổn định, dependency có thể thay fake trong test.

**Điểm review:** module boundary, naming, cách inject dependency.

**Commit đề xuất:** `chore(api): bootstrap flask backend`

---

### BE-01 — Chốt API contract và quy ước HTTP

**Mục tiêu:** thống nhất contract trước khi tạo nhiều endpoint.

**Phạm vi:**

- Chốt JSON naming, datetime UTC ISO 8601, UUID, nullability và enum serialization.
- Error envelope có `code`, `message`, `details`, `request_id`; không trả stack trace.
- Pagination cursor hoặc page/size, sorting whitelist và filter validation.
- Quy tắc status code: 200/201/202/204, 400, 401, 403, 404, 409, 422, 429, 503.
- Chốt content type cho upload ảnh/video và giới hạn kích thước.
- Chốt server-side session mặc định, cookie và CSRF; nếu đổi sang token phải có ADR.
- Chốt contract cho ba search endpoint cùng đi vào một service.
- Chốt lifecycle processing job và error code ổn định.
- Tạo OpenAPI baseline và ví dụ request/response không chứa dữ liệu thật.

**Kiểm thử:** validate OpenAPI, snapshot/contract test cho error envelope và pagination.

**Tiêu chí chấp nhận:** frontend có thể phát triển dựa trên tài liệu mà không cần đọc ORM model; không còn payload mơ hồ cho search, Case và job.

**Commit đề xuất:** `docs(api): define v1 backend contract`

---

### BE-02 — Nền tảng password, session và CSRF

**Mục tiêu:** cung cấp primitive xác thực an toàn trước khi viết route login.

**Phạm vi:**

- Hash password bằng thuật toán phù hợp và cấu hình cost có thể thay đổi.
- Verify password không phân biệt lỗi “username không tồn tại” và “password sai” ở response.
- Opaque server-side session mặc định: ID ngẫu nhiên, lưu hash/token hoặc session ID an toàn, expiry, revoked time, user ID.
- Cookie `HttpOnly`, `SameSite`, `Secure` trong môi trường ngoài local.
- CSRF token cho request thay đổi trạng thái nếu dùng cookie session.
- Rotate session khi login; revoke khi logout, khóa/ngừng user hoặc timeout.
- Clock injectable để test expiry.

**Kiểm thử:** hash/verify, session expiry, fixation, revoke, cookie flags, CSRF thiếu/sai/đúng và không rò thông tin đăng nhập.

**Tiêu chí chấp nhận:** session cũ không dùng lại được sau logout/lock; password không bao giờ lưu/log dạng rõ.

**Commit đề xuất:** `feat(auth): add secure password and session primitives`

---

### BE-03 — UC-01/UC-15: đăng nhập, phiên và đăng xuất

**Mục tiêu:** hiện thực hoàn chỉnh đăng nhập, lấy người dùng hiện tại và đăng xuất cho ba vai trò.

**Endpoint:** `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`.

**Phạm vi:**

- Validate input và normalize username theo policy đã chốt.
- Kiểm tra password, trạng thái tài khoản, role và area của Operator.
- Tạo/revoke phiên; trả thông tin actor tối thiểu cho frontend.
- Middleware nạp actor trên mỗi request và kiểm tra user vẫn active.
- Audit login success, failure, logout và expired session mà không log password.
- Thông báo lỗi không cho phép enumerate account.

**Kiểm thử:** login đủ ba role, password sai, user không tồn tại, locked/inactive, Operator thiếu area, expired/revoked session, logout idempotent và audit event.

**Tiêu chí chấp nhận:** session hợp lệ mới truy cập được route bảo vệ; user bị khóa mất quyền request mới ngay cả khi cookie chưa hết hạn.

**Commit đề xuất:** `feat(auth): implement login session and logout`

---

### BE-04 — Policy phân quyền tập trung

**Mục tiêu:** tránh phân quyền rải rác hoặc phụ thuộc riêng vào decorator role.

**Phạm vi:**

- Policy cho Admin action, Operator current-area search, Case owner, Viewer read-only và media context.
- Decorator chỉ kiểm tra authentication/role thô; resource-level authorization nằm trong service/policy.
- Quy tắc deny-by-default.
- Chuẩn hóa 401/403/404 để hạn chế lộ sự tồn tại của resource.
- Không tin `owner_user_id`, `area_id`, role hoặc camera list do client gửi.
- Test ma trận quyền đầy đủ.

**Kiểm thử:** table-driven test mọi role × action; IDOR test bằng cách thay UUID của user/camera/Case/track.

**Tiêu chí chấp nhận:** thêm route mới mà không gọi policy bị phát hiện qua review/test helper; không có Admin bypass ngoài ma trận quyền.

**Commit đề xuất:** `feat(authz): add centralized backend policies`

---

### BE-05 — UC-02: quản lý Area tham chiếu và tài khoản

**Mục tiêu:** Admin quản lý vòng đời User và gán đúng một Area cho Operator.

**Phạm vi:**

- Danh sách Area có sẵn để Admin chọn; không làm CRUD Area độc lập ở phiên bản này.
- List/detail/create/update User, đổi role, đổi area Operator, lock/unlock và deactivate/delete theo soft-delete policy.
- Chỉ cho phép tạo/gán role Operator hoặc Viewer theo yêu cầu hiện tại; bootstrap Admin qua seed/CLI an toàn.
- Operator phải có đúng một area; Viewer không được nhận area để mở quyền tìm kiếm.
- Thay đổi role/area làm mới hoặc revoke session theo policy đã chốt.
- Không tự chuyển Case khi Operator bị khóa/xóa/đổi role/area.
- Audit mọi thay đổi.

**Kiểm thử:** username trùng, role/area invalid, self-lock policy, đổi Operator→Viewer khi đang sở hữu Case, lock giữ Case, request spoof area và pagination/filter.

**Tiêu chí chấp nhận:** dữ liệu lịch sử tồn tại; mọi mutation có audit; rule Operator-one-area được enforce ở service và database.

**Commit đề xuất:** `feat(admin): implement user account management`

---

### BE-06 — UC-03: quản lý camera và kiểm tra RTSP

**Mục tiêu:** Admin quản lý camera logic dùng cho file video hoặc RTSP.

**Phạm vi:**

- List/detail/create/update/deactivate camera.
- Bắt buộc area lúc tạo; từ chối đổi area ở mọi update.
- RTSP URL/credential là tùy chọn cho camera dùng file video; secret không trả về API.
- Connection test chạy với timeout chặt, không giữ request vô hạn; trả trạng thái có cấu trúc.
- Chặn SSRF: validate scheme `rtsp/rtsps`, host/port và policy mạng phù hợp môi trường.
- Camera deactivated không nhận job/AI data mới nhưng lịch sử không bị xóa.
- Audit create/update/test/deactivate.

**Kiểm thử:** camera không RTSP, RTSP unreachable, credential redaction, duplicate policy, area immutable, SSRF input và deactivate giữ track/Case.

**Tiêu chí chấp nhận:** không có response/log chứa RTSP password; camera file-only vẫn hợp lệ.

**Commit đề xuất:** `feat(admin): implement camera management`

---

### BE-07 — UC-05: registry và cấu hình Detector/Tracker

**Mục tiêu:** Admin chọn cặp Detector/Tracker đã đăng ký cho toàn hệ thống.

**Phạm vi:**

- Registry chỉ đọc cho model đã được code/config đăng ký.
- Trả capability/compatibility metadata cần thiết, không cho upload model.
- Active config dùng chung toàn hệ thống, versioned.
- Validate cặp tương thích trước khi yêu cầu áp dụng.
- Khi apply lỗi, giữ config active trước đó.
- Track đang chạy hoàn tất hoặc timeout theo config cũ; track mới dùng config mới.
- Image/Text Encoder không xuất hiện như lựa chọn Admin.
- Audit requested/applied/failed config.

**Kiểm thử:** model không tồn tại, cặp không tương thích, apply fail rollback, concurrent update/version conflict và track gắn đúng config version.

**Tiêu chí chấp nhận:** không có config Detector/Tracker riêng trên từng camera; active config luôn xác định được.

**Commit đề xuất:** `feat(admin): manage global detector tracker config`

---

### BE-08 — UC-04: bật/tắt AI theo camera

**Mục tiêu:** quản lý việc camera có được tạo dữ liệu AI mới hay không.

**Phạm vi:**

- Endpoint thay đổi `ai_enabled` idempotent.
- Khi bật: camera active, nguồn phù hợp và active AI config hợp lệ.
- Camera file-only có thể bật để nhận processing job dù không có RTSP; RTSP availability chỉ bắt buộc khi khởi chạy RTSP worker.
- Khi tắt: không nhận job/track mới; job đang chạy xử lý theo policy cancel/graceful-stop được khóa trong BE-01.
- Không xóa dữ liệu đã tạo.
- Audit transition và lý do lỗi.

**Kiểm thử:** bật camera inactive, bật thiếu model config, toggle lặp, tắt giữa job và dữ liệu lịch sử còn truy xuất.

**Tiêu chí chấp nhận:** trạng thái mong muốn và trạng thái worker thực tế được phân biệt; không báo “running” chỉ vì flag đã bật.

**Commit đề xuất:** `feat(admin): control camera ai processing state`

---

### BE-09 — API upload video và quản lý processing job

**Mục tiêu:** nhận file video cho demo, tạo job gắn đúng camera và không xử lý trong request.

**Phạm vi:**

- Multipart upload streaming, không đọc toàn file vào RAM.
- Validate extension, MIME/container thực, size, camera active/AI enabled và dung lượng trống.
- Tạo job `QUEUED`; response `202 Accepted` với job ID.
- Staging file private và ngoài Git. Không đưa toàn video vào bucket full-frame chỉ để tạo ảnh kết quả.
- Chốt chính sách: filesystem staging mặc định cho demo hoặc bucket staging riêng; file được xóa sau xử lý theo retention.
- List/detail job, progress, lỗi đã sanitize và nguồn `FILE`/`RTSP`.
- Idempotency key để retry request không tạo nhiều job/file ngoài ý muốn.
- Demo worker concurrency mặc định bằng 1.

**Kiểm thử:** file hợp lệ, MIME giả, file quá lớn, upload ngắt giữa chừng, disk quota, camera ngoài trạng thái, duplicate idempotency key và cleanup staging.

**Tiêu chí chấp nhận:** request kết thúc sau khi file được staging/job được tạo; chưa chạy Detector trong request.

**Commit đề xuất:** `feat(jobs): accept video processing jobs`

---

### BE-10 — Background worker và cổng tích hợp AI pipeline

**Mục tiêu:** xử lý job tuần tự, có thể phục hồi và tách model AI khỏi HTTP API.

**Phạm vi:**

- DB-backed queue mặc định để tránh thêm Redis/Celery khi chưa cần; claim job bằng lock/lease an toàn.
- State machine: `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, và `CANCELLED` nếu đã chốt.
- Heartbeat/lease timeout để reclaim job khi worker chết.
- Interface nguồn frame chung cho file và RTSP.
- Frame sampling trước Detector/Tracker, lưu `source_frame_index` và timestamp nguồn.
- Interface Detector → Tracker → representative frame → RaSa encoder.
- Gọi storage ingestion của STO-11 cho mỗi track hoàn chỉnh.
- Progress/thống kê: frame nguồn, frame đã sample, track thành công/lỗi.
- Graceful shutdown, timeout và giải phóng Track Buffer.

**Kiểm thử:** fake AI adapters deterministic, worker crash/restart, lease expiry, job không chạy trùng, sampling N=10/N=20, timestamp đúng và lỗi từng component.

**Tiêu chí chấp nhận:** một file video giả nhỏ đi qua pipeline fake và tạo track `READY`; web process không chứa vòng lặp xử lý video.

**Commit đề xuất:** `feat(worker): orchestrate sequential video processing`

---

### BE-11 — UC-06: trạng thái hệ thống và processing job

**Mục tiêu:** Admin thấy đúng trạng thái camera, nguồn, worker, job và storage.

**Phạm vi:**

- Tổng hợp operational status, RTSP status, desired AI state, actual worker state và job progress.
- Phân biệt `OFFLINE`, `UNVERIFIED`, `IDLE`, `QUEUED`, `RUNNING`, `ERROR`, `DISABLED` theo contract.
- Health của PostgreSQL/Milvus/MinIO và encoder, nhưng không trả credential/stack trace.
- Filter theo camera/trạng thái; timestamp lần cập nhật gần nhất để tránh hiểu nhầm dữ liệu stale.
- Read-only; không gộp thao tác sửa lỗi vào endpoint status.

**Kiểm thử:** dependency mất kết nối, worker heartbeat stale, camera file-only không RTSP, job fail và partial status.

**Tiêu chí chấp nhận:** Admin phân biệt được “AI đã bật” và “pipeline đang thực sự chạy”.

**Commit đề xuất:** `feat(admin): expose system processing status`

---

### BE-12 — UC-07: chẩn đoán Camera Pipeline/Search Components

**Mục tiêu:** chạy kiểm tra kỹ thuật có giới hạn mà không biến thành chức năng tìm kiếm của Admin.

**Phạm vi:**

- Camera Pipeline diagnostic nhận camera, kiểm tra nguồn frame → Detector → Tracker → Image Encoder.
- Search Components diagnostic không nhận camera, kiểm tra Image Encoder và Text Encoder bằng fixture an toàn.
- Timeout, cancellation và concurrency limit.
- Kết quả theo từng component: success/fail/skipped/inconclusive.
- “Không có người trong frame” là inconclusive, không tự kết luận pipeline hỏng.
- Không persist ảnh/vector diagnostic vào dữ liệu tìm kiếm thật.
- Audit lần chạy và lỗi kỹ thuật quan trọng.

**Kiểm thử:** no frame, no person, detector fail, tracker fail, từng encoder fail, timeout và fixture không làm ô nhiễm Milvus.

**Tiêu chí chấp nhận:** Admin nhận được lỗi đúng component; endpoint không trả danh sách người tìm thấy.

**Commit đề xuất:** `feat(admin): add ai component diagnostics`

---

### BE-13 — UC-08: ghi và tra cứu audit log

**Mục tiêu:** hoàn thiện audit middleware/service cho các thao tác bắt buộc.

**Phạm vi:**

- Event catalog ổn định cho auth, user, Operator area, camera, connection test, AI state/config, Case mutation và technical failure.
- Actor snapshot, target, outcome, timestamp, request ID và metadata đã redact.
- Ghi cả success/failure tại boundary phù hợp; audit failure không làm mutation chính bị báo thành công sai.
- Query theo thời gian, actor, event type/outcome và pagination.
- Không cho sửa/xóa audit qua UI API.
- Không ghi từng lượt tìm kiếm Operator trong phiên bản này.

**Kiểm thử:** độ phủ event theo use case, filter, pagination, secret redaction, log injection và search không tạo audit business event.

**Tiêu chí chấp nhận:** Admin truy vết ai làm gì và kết quả ra sao mà không đọc application log thô.

**Commit đề xuất:** `feat(admin): implement audit trail queries`

---

### BE-14 — Chuẩn bị truy vấn ảnh/văn bản/thuộc tính

**Mục tiêu:** biến ba kiểu input thành query embedding hợp lệ qua interface thống nhất.

**Phạm vi:**

- Image endpoint: validate ảnh crop, decode an toàn, orientation, kích thước, channel và preprocessing theo RaSa.
- Text endpoint: validate length/encoding; chốt cách xử lý tiếng Việt trước khi tuyên bố hỗ trợ đầy đủ.
- Attribute endpoint: whitelist thuộc tính và prompt builder deterministic sang câu tiếng Anh có kiểm soát.
- Gateway tới RaSa Image/Text Encoder, timeout và model version check.
- Normalize/vector dimension theo cùng policy lúc lập chỉ mục.
- Không persist raw query image, text hoặc embedding mặc định.
- Không nhận đồng thời nhiều mode trong một request.

**Kiểm thử:** ảnh hỏng/bomb/quá lớn, text rỗng/quá dài, attribute lạ/conflict, prompt snapshot, encoder timeout/sai dimension và không log query nhạy cảm.

**Tiêu chí chấp nhận:** ba mode trả cùng một `QueryEmbedding` contract kèm encoder version; lỗi input tách biệt lỗi model.

**Commit đề xuất:** `feat(search): prepare image text and attribute queries`

---

### BE-15 — UC-09: tìm kiếm có lọc và phân quyền

**Mục tiêu:** tìm top track trong đúng area hiện tại của Operator.

**Phạm vi:**

- Chỉ Operator gọi được search.
- Lấy area từ actor/session; không nhận area để mở rộng quyền.
- Camera filter phải là tập con của camera active/hợp lệ thuộc area.
- Validate time range, timezone và `top_k ∈ {4,8,12,16}`.
- Filter area/camera/time trong Milvus **trước** top-k.
- Hydrate metadata PostgreSQL, chỉ lấy track `READY` và recheck quyền.
- Response sắp score giảm dần, có `track_id`, camera, area, appeared time, media link và Matching Score.
- Không dùng threshold và không persist Matching Score.
- Nếu ít hơn top-k, trả số thực có; stale vector bị loại và metric hóa.

**Kiểm thử:** hai area với vector tương tự, camera ngoài quyền, time boundary, từng top-k hợp lệ/không hợp lệ, score ordering, zero results, stale Milvus ID và encoder version mismatch.

**Tiêu chí chấp nhận:** không có dữ liệu ngoài area trong body, count hoặc media; database không xuất hiện cột/bản ghi score.

**Commit đề xuất:** `feat(search): implement authorized person retrieval`

---

### BE-16 — UC-10: trình bày kết quả và media có quyền

**Mục tiêu:** Operator xem crop và full frame có bbox trong ngữ cảnh tìm kiếm hiện tại.

**Phạm vi:**

- DTO kết quả nhất quán cho ba search mode.
- Endpoint crop động và full frame annotated theo context quyền current-area.
- Không nhận object key/bbox tùy ý từ client.
- Streaming có content type, size limit, cache policy và ETag/checksum phù hợp.
- Metadata vẫn có thể hiển thị nếu ảnh thiếu; error code ảnh rõ ràng.
- Sorting/filter UI-side không tạo quyền truy cập mới; nếu backend hỗ trợ sort/filter lại thì whitelist rõ ràng.

**Kiểm thử:** bbox edge/corrupt, object missing, IDOR track, Operator đổi area sau search, cache không làm lộ ảnh giữa user và full frame không ghi ngược vào MinIO.

**Tiêu chí chấp nhận:** media luôn qua policy; person crop không được persist.

**Commit đề xuất:** `feat(search): expose authorized result media`

---

### BE-17 — UC-11: quản lý Case và CaseResult

**Mục tiêu:** Operator tạo/quản lý Case của mình và lưu track đã chọn.

**Phạm vi:**

- List/detail Case của Operator hiện tại.
- Tạo Case với title/note; owner luôn lấy từ session.
- Patch title/note; không có field status/area/owner trong payload.
- Thêm `track_id` vào Case sau khi kiểm tra owner Case và quyền current-area đối với track ở thời điểm lưu.
- Mỗi POST thành công tạo `CaseResult` mới, kể cả track trùng.
- Không nhận/lưu Matching Score hoặc `result_ref`.
- Xóa đúng `case_result_id`; không xóa track/frame/vector.
- Media trong Case kiểm tra Case owner thay vì area hiện tại.

**Kiểm thử:** spoof owner, Case người khác, track ngoài area, duplicate save, xóa một duplicate, concurrent patch, Operator đổi area vẫn xem Case cũ và score field bị từ chối/ignore theo contract đã chốt.

**Tiêu chí chấp nhận:** Case chứa title, note và các CaseResult; không có trạng thái, area hoặc score.

**Commit đề xuất:** `feat(case): implement operator case management`

---

### BE-18 — UC-12, UC-13, UC-14: Viewer dashboard và xem Case

**Mục tiêu:** Viewer đọc dữ liệu nghiệp vụ toàn hệ thống mà không thể thay đổi.

**Phạm vi:**

- UC-12: dashboard gồm tổng số Case, tổng số row CaseResult kể cả duplicate và Case gần đây.
- UC-13: list/filter Case theo thời gian/Operator; detail có owner snapshot và result list.
- UC-14: xem metadata và media Case qua context `case_id + case_result_id`.
- Nếu ảnh thiếu, trả metadata snapshot và trạng thái ảnh không khả dụng.
- Không hiển thị Matching Score vì score không được lưu trong Case.
- Route mutation trả 403 cho Viewer.

**Kiểm thử:** số đếm duplicate, recent ordering, filter, inactive/deleted Operator vẫn hiển thị lịch sử, missing image và Viewer không thể gọi search/case mutation/admin API.

**Tiêu chí chấp nhận:** Viewer thấy toàn bộ Case chỉ đọc; response không có score cũ/giả.

**Commit đề xuất:** `feat(viewer): add dashboard and read-only case access`

---

### BE-19 — Quy tắc lịch sử khi User/Camera thay đổi vòng đời

**Mục tiêu:** kiểm chứng tập trung các tình huống cross-use-case dễ gây mất dữ liệu.

**Phạm vi:**

- Khóa/deactivate/delete mềm User revoke quyền request mới nhưng giữ owner/audit history.
- Operator đổi area: search mới theo area mới, Case cũ vẫn theo owner.
- Camera deactivate: không nhận job/track mới, nhưng CaseResult và media lịch sử còn xem được.
- Đổi tên camera/area không làm thay snapshot trong CaseResult nếu policy dùng snapshot.
- Xóa CaseResult không làm thay dữ liệu track.
- Tài nguyên được Case tham chiếu không được cleanup tự động.

**Kiểm thử:** scenario test cho từng transition trên, bao gồm session đang mở và request song song.

**Tiêu chí chấp nhận:** không có thao tác quản trị nào vô tình làm Viewer mất Case hoặc làm lịch sử đổi nghĩa.

**Commit đề xuất:** `test: enforce historical data lifecycle rules`

---

### BE-20 — Idempotency, concurrency và error handling

**Mục tiêu:** backend hành xử dự đoán được khi retry, request song song hoặc dependency lỗi.

**Phạm vi:**

- Idempotency key cho upload/job và các operation có nguy cơ lặp ngoài ý muốn; CaseResult mặc định mỗi lần bấm là row mới nên không tự deduplicate nếu không cùng idempotency key.
- Optimistic locking/version conflict cho AI config, user/camera update và Case update khi cần.
- Timeout/circuit-breaker mức hợp lý cho RTSP, encoder, Milvus và MinIO.
- Error taxonomy domain → HTTP; dependency unavailable trả 503, input invalid 422, conflict 409.
- Transaction rollback và compensation cho operation nhiều bước.
- Request ID xuyên web → worker → storage log.

**Kiểm thử:** double submit, concurrent update, retry sau timeout, dependency partial failure, malformed error từ adapter và không trả stack trace.

**Tiêu chí chấp nhận:** cùng lỗi cho cùng error code ổn định; retry an toàn không tạo job/object ngoài ý muốn.

**Commit đề xuất:** `feat(api): harden idempotency concurrency and errors`

---

### BE-21 — Hardening bảo mật API và upload

**Mục tiêu:** giảm các rủi ro thực tế trước khi nối frontend/demo.

**Phạm vi:**

- Security headers, CORS allowlist, cookie policy, CSRF và trusted proxy configuration.
- Rate limit login, diagnostic, RTSP test, upload và search.
- Upload size/time limit, file signature validation, decompression bomb protection và filename không được dùng làm path.
- SSRF protection cho RTSP test.
- SQL/filter injection test, đặc biệt Milvus expression builder.
- IDOR test cho User/Camera/Track/Case/CaseResult/media.
- Secret redaction; không trả internal host, stack trace hoặc model path.
- Dependency vulnerability scan và pin version.

**Kiểm thử:** security suite tự động, negative permission matrix, malicious filenames/content type, CSRF/CORS và rate-limit behavior.

**Tiêu chí chấp nhận:** các route nhạy cảm có limit phù hợp; không có bucket/object URL public; không bypass policy bằng ID trực tiếp.

**Commit đề xuất:** `security: harden backend api boundaries`

---

### BE-22 — Logging, metric, tracing và readiness

**Mục tiêu:** quan sát được lỗi request, job và dependency mà không lộ dữ liệu nhạy cảm.

**Phạm vi:**

- Structured log với timestamp, level, service, request/job/track ID và event.
- Correlation ID từ API tới worker/storage.
- Metric: request latency/error, login failure, active sessions, queue depth, job duration, track counts, encoder/search latency, MinIO/Milvus errors.
- Liveness chỉ phản ánh process; readiness phản ánh dependency bắt buộc theo vai trò web/worker.
- Worker heartbeat và trạng thái model loaded.
- Log retention/rotation cho máy demo.
- Không dùng audit log thay application log hoặc ngược lại.

**Kiểm thử:** log capture/redaction, metric increment, readiness khi từng dependency down và request ID xuyên fake job.

**Tiêu chí chấp nhận:** khi E2E lỗi có thể xác định request/job/component liên quan mà không bật debug production.

**Commit đề xuất:** `feat(ops): add backend observability and readiness`

---

### BE-23 — Test contract, integration, authorization và E2E

**Mục tiêu:** chứng minh toàn bộ backend thỏa use case và quy tắc quyền.

**Các lớp test:**

- Unit: service, policy, validator, state machine, prompt builder.
- Route/contract: status, schema, error code, OpenAPI.
- Integration: PostgreSQL/Milvus/MinIO và worker fake-AI.
- Authorization: role matrix, area isolation, owner isolation, IDOR media.
- Failure injection: dependency chết, worker crash, retry, missing object/vector.
- E2E: login → admin setup → job → search → media → Case → Viewer.

**Kịch bản E2E bắt buộc:**

1. Admin tạo hai Operator ở hai area và camera tương ứng.
2. Admin tạo job video; fake pipeline tạo track `READY`.
3. Operator A tìm kiếm và không nhận track area B.
4. Operator A mở crop/frame, lưu cùng track hai lần vào Case.
5. Admin đổi area Operator A; search mới theo area mới nhưng Case cũ còn mở được.
6. Viewer dashboard đếm hai CaseResult, xem Case/media và không thấy Matching Score.
7. Camera/User inactive không làm mất lịch sử.
8. Milvus/MinIO unavailable tạo lỗi chuẩn và có khả năng retry/recover.

**Lệnh test mục tiêu:**

```powershell
python -m pytest -m unit
python -m pytest -m contract
python -m pytest -m integration
python -m pytest -m security
python -m pytest -m e2e
```

**Tiêu chí chấp nhận:** test chạy lặp lại từ môi trường sạch, không phụ thuộc thứ tự, fixture không dùng dữ liệu/video thật.

**Commit đề xuất:** `test: cover backend workflows end to end`

---

### BE-24 — Đo hiệu năng và tài nguyên Backend

**Mục tiêu:** xác nhận Flask, worker và storage phù hợp máy demo.

**Phạm vi đo:**

- p50/p95/p99 login, CRUD, Case list và search API.
- Search latency tách query encoding, Milvus, PostgreSQL hydrate và media fetch.
- Upload throughput/memory; chứng minh upload streaming.
- RAM/CPU web process, worker idle/model-loaded và toàn stack.
- Queue throughput với worker concurrency 1.
- Hành vi khi nhiều request search/media đồng thời trong giới hạn demo.
- Capacity gần quy mô dữ liệu từ 7 video.

**Phương pháp:** script load deterministic, ghi machine spec, dataset size, model fake/real, cold/warm run và ngưỡng chấp nhận sau baseline đầu.

**Tiêu chí chấp nhận:** không OOM, không đọc toàn video vào RAM, response tương tác ổn định; bottleneck có số đo và phương án trình bày khi phản biện.

**Commit đề xuất:** `perf: establish backend performance baseline`

---

### BE-25 — Đóng gói, cấu hình triển khai và runbook

**Mục tiêu:** chạy lại được backend/web/worker trong buổi demo và phục hồi có kiểm soát.

**Phạm vi:**

- Container hoặc quy trình chạy web và worker riêng.
- Production-style WSGI server; không dùng Flask development server để demo chính thức nếu không cần.
- Biến môi trường, secret injection, startup validation và migration command.
- Thứ tự start: storage → migrate/seed → worker → API; readiness gate.
- Graceful shutdown web/worker; job lease có thể phục hồi.
- Runbook upload/xử lý tuần tự 7 video, chuẩn bị dữ liệu trước và trình diễn một video.
- Runbook RTSP giả lập tại nhà, lưu log/số đo/bằng chứng.
- Runbook backup/restore từ STO-19, retry/reconcile và xử lý disk đầy/model load fail.
- Release checklist và rollback ứng dụng/migration phù hợp.

**Kiểm thử:** dựng môi trường sạch theo đúng tài liệu, chạy migration, E2E smoke, restart worker giữa job và restore một bản backup test.

**Tiêu chí chấp nhận:** một người khác có thể làm theo runbook để chạy demo mà không cần biết chi tiết code nội bộ.

**Commit đề xuất:** `docs: add backend deployment and demo runbook`

## 11. Ma trận kiểm thử tổng thể

| Loại test | Nội dung chính | Khi chạy |
| --- | --- | --- |
| Unit | Validator, policy, service, state machine, prompt builder | Mọi task code |
| Contract | OpenAPI, request/response, error code, pagination | Mọi thay đổi API |
| Route | Flask test client, auth/cookie/CSRF/status | Mọi endpoint |
| Integration | PostgreSQL, Milvus, MinIO, worker fake-AI | Task có storage/I/O |
| Authorization | Role, area, Case owner, Viewer read-only, IDOR media | BE-04 trở đi |
| Failure injection | Timeout, dependency down, worker crash, retry | BE-10, BE-20, BE-23 |
| Security | Upload, SSRF, CSRF, CORS, rate limit, injection | BE-21 và trước release |
| E2E | Admin → job → search → Case → Viewer | BE-23 và trước demo |
| Performance | Latency, memory, queue, search/media | BE-24 và khi đổi model |
| Deployment smoke | Migrate, start, health, restart, restore | BE-25 và trước demo |

## 12. Checklist review trước mỗi commit

- [ ] Task ở `READY_FOR_REVIEW` và dependency đã `DONE`.
- [ ] Diff chỉ chứa thay đổi thuộc task.
- [ ] API contract/OpenAPI đã cập nhật nếu endpoint thay đổi.
- [ ] Unit test và các integration/security test liên quan đều đạt.
- [ ] Có negative test cho authentication/authorization.
- [ ] Không persist hoặc trả Matching Score ngoài lượt tìm kiếm.
- [ ] Không tin area/owner/role/object key do client gửi.
- [ ] Không có secret, video/frame thật, raw embedding hoặc `.env` được stage.
- [ ] Log/error response đã được kiểm tra redaction.
- [ ] Người thực hiện đã review và xác nhận.
- [ ] Sau commit đã ghi SHA vào bảng theo dõi.

## 13. Nhật ký thực hiện

Thêm một mục cho mỗi vòng triển khai/review:

```text
### YYYY-MM-DD — BE-XX
- Trạng thái: IN_PROGRESS | READY_FOR_REVIEW | DONE | BLOCKED
- Use case/endpoint liên quan:
- Thay đổi chính:
- File quan trọng:
- Test đã chạy:
- Kết quả test:
- Rủi ro hoặc điểm cần review:
- Chỉnh sửa sau review:
- Commit SHA (chỉ điền sau khi DONE):
```

## 14. Các quyết định cần khóa ở BE-01

- Server-side session lưu trong PostgreSQL hay một session store khác; mặc định PostgreSQL để không thêm Redis ở bản đầu.
- CSRF strategy và CORS origin của frontend.
- Pagination dùng cursor hay page/size cho từng danh sách.
- Một endpoint search đa content type hay ba endpoint riêng; mặc định ba endpoint dùng chung service.
- Video upload staging dùng filesystem private hay bucket riêng; retention sau khi job hoàn tất.
- Giới hạn ảnh/video, text query, timeout encoder và timeout RTSP test.
- Job cancel/graceful-stop semantics khi Admin tắt AI giữa lúc xử lý.
- Chuẩn dịch/tiền xử lý mô tả tiếng Việt trước RaSa Text Encoder.
- Policy 403/404 cho tài nguyên tồn tại nhưng không có quyền.
- Có cần presigned URL hay luôn stream media qua Flask; mặc định stream qua backend.

Các câu hỏi trên không ngăn BE-00, nhưng phải được quyết định và review trước khi các endpoint nghiệp vụ được triển khai.

## 15. Nhật ký đã thực hiện

### 2026-09-25 — BE-00

- Trạng thái: `DONE`.
- Use case/endpoint liên quan: skeleton, `GET /health/live`, `GET /api/v1/ping`.
- Thay đổi chính: tạo Flask application factory, blueprint health/API v1, JSON HTTP error cơ bản, dependency container, cấu hình environment, API/worker entrypoint và project tooling.
- File quan trọng: `backend/pyproject.toml`, `backend/src/person_search/app.py`, `backend/src/person_search/api/`, `backend/tests/unit/test_app_factory.py`, `backend/README.md`.
- Test đã chạy: `pytest -m unit`, toàn bộ `pytest` với coverage, `ruff check .`, `compileall src`, worker entrypoint.
- Kết quả test: 16 test đạt; coverage 79%; Ruff không phát hiện lỗi; compile và worker entrypoint thành công.
- Rủi ro hoặc điểm cần review: cấu trúc module, dependency injection, dependency version range và việc giữ `ping` như endpoint smoke tạm thời.
- Chỉnh sửa sau review: người thực hiện yêu cầu commit toàn bộ workspace.
- Commit: root commit `first commit`; SHA được xác minh bằng `git log` sau khi hoàn tất amend.

### 2026-09-25 — BE-02, BE-03

- Trạng thái: `READY_FOR_REVIEW`.
- Use case/endpoint liên quan: UC-01, UC-15; `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.
- Thay đổi chính: migration `20260925_0005` thêm bảng `auth_sessions` và cột `users.last_login_at`; hash Argon2id; session opaque lưu SHA-256 trong PostgreSQL, hết hạn tuyệt đối 12h và idle 30 phút (cấu hình qua `PERSON_SEARCH_SESSION_TTL_MINUTES`, `PERSON_SEARCH_SESSION_IDLE_MINUTES`); cookie `ps_session` `HttpOnly`/`SameSite=Lax`/`Secure` ngoài development; CSRF token = HMAC từ session token, gửi qua header `X-CSRF-Token`; rotate session khi login; user bị khóa mất quyền ở request kế tiếp; audit login thành công/thất bại, logout, session hết hạn; error envelope có `request_id`; decorator `require_auth(*roles)` thô (policy theo resource vẫn thuộc BE-04); CLI `person-search-user` để bootstrap Admin và tạo tài khoản test.
- File quan trọng: `backend/src/person_search/services/auth.py`, `backend/src/person_search/auth/`, `backend/src/person_search/api/v1/auth.py`, `backend/src/person_search/api/errors.py`, `backend/migrations/versions/20260925_0005_auth_sessions.py`.
- Test đã chạy: `pytest` toàn bộ, `ruff check .`, `compileall src`, integration migration trên database PostgreSQL tạm, E2E thủ công qua Vite proxy và headless browser.
- Kết quả test: 248 unit test đạt; 6 integration migration test đạt (7 test cần Milvus/MinIO bị skip); login/me/logout/CSRF/audit xác nhận trên database thật.
- Rủi ro hoặc điểm cần review: CSRF dẫn xuất từ session token thay vì lưu riêng; logout yêu cầu CSRF khi còn cookie; username chuẩn hóa về chữ thường; chưa có rate limit login (BE-21).
- Chỉnh sửa sau review:
- Commit SHA (chỉ điền sau khi DONE):
