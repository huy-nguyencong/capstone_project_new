# Roadmap API Backend ↔ Frontend

> Kế hoạch endpoint mà backend (Flask, `backend/`) sẽ xây và frontend (React/Vite, `frontend/`) sẽ dùng để thay dữ liệu mock. Viết ngày 2026-09-25 dựa trên code hiện tại và `files/backend_implementation_plan.md`. Mã task `BE-xx` tham chiếu kế hoạch đó.

## 1. Hiện trạng

### Backend

- Đã có: application factory, `GET /health/live`, `GET /health/ready`, `GET /health/storage`, `GET /api/v1/ping`, error handler JSON tối thiểu.
- Tầng storage và service đã xong, **chưa có route**:
  - `CaseService`: tạo/sửa Case, thêm/xóa CaseResult, list/detail, `viewer_dashboard` (cursor pagination).
  - `TrackSearchService`: search theo embedding, lọc area/camera/thời gian, `top_k`.
  - `TrackImageService`: ảnh crop / full frame cho kết quả search và kết quả trong Case.
  - `AuditLogService`: query audit theo thời gian, actor, event type, kết quả (cursor pagination) + `AuditEvent` catalog.
  - `StorageStatusService`: snapshot track/outbox/health từng kho dữ liệu.
  - `TrackIngestionService`: ghi track vào PostgreSQL/MinIO/Milvus (dùng bởi worker).
- Chưa có: auth/session, policy, quản lý user/camera, AI config, processing job, worker thật, encoder gateway, diagnostics.

### Frontend

- Toàn bộ dữ liệu lấy từ `src/mocks/*` qua `AppStoreProvider`; `apiService.js` (axios, Bearer token trong `localStorage`) đã có nhưng chưa được gọi.
- Màn hình theo vai trò:
  - Admin: Tài khoản, Camera, Xử lý AI, Mô hình AI, Trạng thái hệ thống, Kiểm tra AI, Nhật ký hệ thống.
  - Operator: Tìm kiếm người, Case của tôi.
  - Viewer: Tổng quan, Hồ sơ vụ việc.
- Chưa có màn hình upload video / theo dõi processing job.

## 2. Chênh lệch cần xử lý trước khi nối API

| # | Frontend hiện tại | Quyết định backend | Hướng xử lý |
| --- | --- | --- | --- |
| G1 | Bearer token lưu `localStorage` | Server-side session + cookie `HttpOnly` + CSRF | FE bật `withCredentials`, gửi header `X-CSRF-Token`, bỏ `tokenStorage`. Cookie còn cần để `<img src>` tải ảnh crop/frame có kiểm tra quyền (thẻ `img` không gửi được header Bearer). |
| G2 | `top_k` nhập tự do 1–100, mặc định 24 | `top_k ∈ {4, 8, 12, 16}` | FE đổi input thành select 4/8/12/16, mặc định 8. |
| G3 | Case item lưu `score` | Matching Score chỉ có trong response search, không lưu vào Case | FE bỏ `score` khỏi Case item và `CaseDetail`/`CaseItemGrid`. |
| G4 | `AddToCaseDialog` coi track đã có là trùng | Mỗi lần thêm tạo `CaseResult` mới, cho phép trùng `track_id` | Giữ tag "Đã có" chỉ để thông báo, không chặn thao tác. |
| G5 | Role/status viết thường (`admin`, `active`, `online`…) | Enum viết hoa (`ADMIN`, `ACTIVE`, `ONLINE`…) | Tạo `src/services/mappers.js` map enum API → key UI trong `constants/status.js`. |
| G6 | Area là index số (`area: 0`) | Area có `id` (UUID), `code`, `name` | FE dùng `area_id` + gọi `GET /areas`. |
| G7 | ID dạng `u2`, `c1`, `CS-0142`, `T-40327` | UUID | FE hiển thị UUID rút gọn (8 ký tự đầu). Nếu cần mã Case đẹp, thêm cột `code` ở migration riêng (câu hỏi mở Q3). |
| G8 | Camera hiển thị RTSP URL | Không bao giờ trả RTSP credential | API trả `rtsp_url_masked`; FE chỉ gửi URL mới khi sửa. |
| G9 | Trạng thái camera gộp 1 field (`online/offline/unverified/unknown/retired`) + `aiState` | Tách `status` (vòng đời), `rtsp_status`, `ai_enabled`, trạng thái worker thực tế | Mapper FE tính trạng thái hiển thị (bảng mục 4.3). |
| G10 | Thuộc tính → prompt tiếng Việt build ở FE | Prompt builder deterministic ở backend, sinh câu tiếng Anh | FE gửi thuộc tính có cấu trúc; backend trả `prompt` để FE hiển thị nhãn truy vấn. |
| G11 | Không có màn upload video | Demo chạy bằng file video → processing job | FE thêm trang "Xử lý video" cho Admin (Phase 4). |
| G12 | Diagnostic outcome `ok/warn/fail/skip` | `SUCCESS/INCONCLUSIVE/FAILED/SKIPPED` | Map 1–1 trong mapper. |
| G13 | Metric camera `fps`, `bitrate`, `procFps`, `latency` | Chưa có nguồn dữ liệu | Để nullable; worker heartbeat bổ sung sau (Phase 8). FE hiển thị "—" khi null. |
| G14 | Audit type là chuỗi tiếng Việt | `event_type` dạng `auth.login`, `case.result_added`… | FE map `event_type` → nhóm + nhãn tiếng Việt. |

## 3. Quy ước chung (BE-01)

- Base URL: `/api/v1`. Health nằm ngoài prefix: `/health/*`.
- JSON dùng `snake_case`; thời gian là chuỗi ISO 8601 UTC (`2026-09-25T02:42:11Z`); ID là UUID string.
- FE gửi khoảng ngày theo giờ địa phương, đổi sang UTC trước khi gọi API: `from` = 00:00:00 +07:00, `to` = 23:59:59.999 +07:00.
- Danh sách dùng cursor: query `?limit=20&cursor=<opaque>`, response `{ "items": [...], "next_cursor": "..." | null }`. Khớp `CaseService` và `AuditLogService` hiện có.
- Error envelope:

```json
{
  "error": {
    "code": "case_not_found",
    "message": "Không tìm thấy Case.",
    "details": { "field_errors": { "title": "Không được để trống." } },
    "request_id": "7f0c1d2e-..."
  }
}
```

- Status code: `200` đọc/sửa, `201` tạo, `202` job đã nhận, `204` xóa/logout, `400` request sai định dạng, `401` chưa đăng nhập/phiên hết hạn, `403` không đủ quyền, `404` không tồn tại hoặc không được phép biết, `409` xung đột version/trùng, `413` file quá lớn, `422` validate lỗi, `429` rate limit, `503` dependency (Milvus/MinIO/encoder) lỗi.
- Session: cookie `ps_session` (`HttpOnly`, `SameSite=Lax`, `Secure` ngoài local). CSRF token trả trong `GET /auth/me`, `POST /auth/login` và `POST /auth/refresh`; mọi request `POST/PUT/PATCH/DELETE` gửi header `X-CSRF-Token`.
- Optimistic locking: resource có thể sửa đồng thời trả `version`; request sửa gửi lại `version`, lệch thì `409 version_conflict`.
- Media: luôn stream qua backend, `Cache-Control: private, no-store`, không có URL MinIO public.

### Thay đổi phía FE cho quy ước

- `apiService.js`: `withCredentials: true`, interceptor gắn `X-CSRF-Token`, đọc `error.code`/`error.message` từ envelope mới, bỏ `tokenStorage`.
- Thêm `src/services/api/` chia theo nhóm (`auth.js`, `users.js`, `cameras.js`, `ai.js`, `jobs.js`, `search.js`, `cases.js`, `viewer.js`, `monitor.js`) và `mappers.js`.
- `AppStoreProvider` chỉ giữ `me` + CSRF token; dữ liệu danh sách chuyển sang hook fetch theo trang (có thể dùng TanStack Query để cache/refetch).
- `vite.config.js`: proxy `/api` và `/health` về Flask để cookie cùng origin khi dev.

## 4. Danh mục endpoint theo phase

Cột **BE sẵn có** cho biết service đã tồn tại chưa: `service` = chỉ cần viết route + policy; `mới` = cần viết cả service.

### Phase 1 — Xác thực (BE-02, BE-03, BE-04) · ĐÃ XONG, chờ review

Backend và frontend đã nối xong. Riêng BE-04 mới có `require_auth(*roles)` kiểm tra role thô; policy theo resource làm cùng các phase sau.

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | Public | mới | `LoginPage` |
| GET | `/auth/me` | Đã đăng nhập | mới | `AppStoreProvider` khi khởi động, `RequireAuth` |
| POST | `/auth/refresh` | Đã đăng nhập | mới | `AppStoreProvider` theo lịch từ server |
| POST | `/auth/logout` | Đã đăng nhập | mới | `UserCard` |

`POST /auth/login`

```json
{ "username": "khoa.tran", "password": "••••••" }
```

`200`:

```json
{
  "user": {
    "id": "uuid",
    "username": "khoa.tran",
    "display_name": "Trần Minh Khoa",
    "role": "OPERATOR",
    "area": { "id": "uuid", "code": "GATE-A", "name": "Gate A" }
  },
  "csrf_token": "..."
}
```

Lỗi FE cần xử lý (thông điệp đang có trong `AppStoreProvider.login`):

- `401 invalid_credentials`: sai username hoặc password, không phân biệt hai trường hợp.
- `403 account_disabled`: tài khoản `LOCKED`/`INACTIVE`/`DELETED`.
- `503 service_unavailable`: lỗi hệ thống.

`GET /auth/me` trả cùng shape `user` + `csrf_token` + `refresh_after_seconds`; `401` khi phiên hết hạn hoặc user bị khóa (FE chuyển về `/login` qua `onUnauthorized`). `POST /auth/refresh` yêu cầu CSRF, thu hồi token hiện tại, đặt cookie mới và trả session payload mới; token đã hết hạn hoặc bị thu hồi không thể refresh. `POST /auth/logout` trả `204`, idempotent.

Tiêu chí xong phase: FE bỏ `mocks/users.js` khỏi luồng đăng nhập, route guard dựa trên `GET /auth/me`.

### Phase 2 — Area và tài khoản (BE-05) · ĐÃ XONG, chờ review

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/areas` | Admin, Operator | mới (bảng + seed đã có) | `UserDialog`, `CameraDialog`, `CamerasPage` filter |
| GET | `/admin/users` | Admin | mới | `UsersPage` |
| POST | `/admin/users` | Admin | mới | `UserDialog` (tạo) |
| GET | `/admin/users/{id}` | Admin | mới | `UserDialog` (sửa) |
| PATCH | `/admin/users/{id}` | Admin | mới | `UserDialog` (sửa) |
| POST | `/admin/users/{id}/lock` | Admin | mới | `UsersPage` nút khóa |
| POST | `/admin/users/{id}/unlock` | Admin | mới | `UsersPage` nút mở khóa |
| POST | `/admin/users/{id}/deactivate` | Admin | mới | `UsersPage` nút ngừng hoạt động |

- `GET /admin/users?role=OPERATOR&status=LOCKED&q=khoa&limit=20&cursor=` — hỗ trợ đúng các filter `UsersPage` đang có (`all`, theo role, bị khóa) và ô tìm kiếm.
- User item: `id`, `username`, `display_name`, `role`, `status`, `area` (object hoặc `null`), `last_login_at`, `created_at`, `version`.
- `POST /admin/users`: `username`, `display_name`, `password`, `role` (`OPERATOR`|`VIEWER`), `area_id` (bắt buộc với Operator, cấm với Viewer).
- `PATCH /admin/users/{id}`: `display_name`, `role`, `area_id`, `password` (reset), `version`. Đổi role/area revoke session đang mở của user đó.
- Lỗi: `409 username_taken`, `422 operator_area_required`, `422 viewer_area_forbidden`, `409 cannot_lock_self`.
- Chọn `/deactivate` thay cho `DELETE`: dữ liệu lịch sử (Case owner, audit) phải còn.

### Phase 3 — Camera, AI state, cấu hình Detector/Tracker (BE-06, BE-07, BE-08) · ĐÃ TRIỂN KHAI

Backend + bốn màn hình quản trị đã nối API. Migration `20260925_0007`; [hướng dẫn cấu hình và kiểm thử](phase-3-setup.md), [OpenAPI Phase 3](openapi-phase-3.json). Registry mặc định rỗng; worker và chẩn đoán thực tế thuộc phase sau.

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/admin/cameras` | Admin | mới | `CamerasPage`, `AiProcessingPage`, `DiagnosticsPage` |
| POST | `/admin/cameras` | Admin | mới | `CameraDialog` (tạo) |
| GET | `/admin/cameras/{id}` | Admin | mới | `CameraDialog` (sửa) |
| PATCH | `/admin/cameras/{id}` | Admin | mới | `CameraDialog` (sửa) |
| POST | `/admin/cameras/{id}/retire` | Admin | mới | `CamerasPage` nút loại khỏi vận hành |
| POST | `/admin/cameras/{id}/connection-tests` | Admin | mới | `CamerasPage` nút kiểm tra, `CameraDialog` |
| PUT | `/admin/cameras/{id}/ai-state` | Admin | mới | `AiProcessingPage` switch |
| GET | `/admin/ai/models` | Admin | mới | `ModelsPage`, `DiagnosticsPage` |
| GET | `/admin/ai/config` | Admin | mới | `ModelsPage`, `AiProcessingPage` header |
| PUT | `/admin/ai/config` | Admin | mới | `ModelsPage` nút áp dụng |

Camera item:

```json
{
  "id": "uuid",
  "code": "A-01",
  "name": "A-01 Cổng chính",
  "area": { "id": "uuid", "code": "GATE-A", "name": "Gate A" },
  "status": "ACTIVE",
  "rtsp_status": "ONLINE",
  "rtsp_url_masked": "rtsp://***@10.0.1.11:554/stream1",
  "has_rtsp": true,
  "ai_enabled": true,
  "last_checked_at": "2026-09-25T02:40:00Z",
  "version": 3
}
```

- `GET /admin/cameras?area_id=&status=&limit=&cursor=`.
- `POST`: `code`, `name`, `area_id`, `rtsp_url` (tùy chọn, camera chỉ dùng file video được phép bỏ trống). `PATCH`: `name`, `rtsp_url`, `version`; gửi `area_id` trả `422 camera_area_immutable`.
- `POST /connection-tests` chạy có timeout (mặc định 10s), trả `200 { "rtsp_status": "ONLINE" | "OFFLINE" | "ERROR", "message": "...", "checked_at": "..." }`. Camera không có RTSP trả `422 camera_has_no_rtsp`.
- `PUT /ai-state` body `{ "enabled": true }`, idempotent. Lỗi: `409 camera_not_active`, `409 ai_config_missing`.
- `GET /admin/ai/models`:

```json
{
  "detectors": [{ "id": "yolov8m", "name": "YOLOv8-m", "description": "...", "meta": "640 px · ~9 ms/frame", "available": true }],
  "trackers": [{ "id": "bytetrack", "name": "ByteTrack", "description": "...", "meta": "...", "available": true, "compatible_detectors": ["yolov8m", "yolov8x"] }],
  "encoder": { "name": "RaSa", "version": "...", "dimension": 256 }
}
```

- `GET/PUT /admin/ai/config`: `{ "detector_id", "tracker_id", "version", "applied_at" }`. `PUT` lỗi `422 incompatible_model_pair`, `422 model_unavailable`, `409 version_conflict`; apply lỗi thì giữ config cũ.

### Phase 4 — Upload video và processing job (BE-09, BE-10) · ĐÃ TRIỂN KHAI

Đã có API upload/job, worker tuần tự với fake AI opt-in và trang **Xử lý video**. Migration `20260925_0008`; [thiết lập và chính sách vận hành](phase-4-setup.md), [OpenAPI Phase 4](openapi-phase-4.json). Adapter Detector/Tracker/RaSa thật nối qua interface pipeline sau; demo dùng encoder/collection riêng.

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| POST | `/admin/cameras/{id}/processing-jobs` | Admin | mới | Trang mới "Xử lý video" |
| GET | `/admin/processing-jobs` | Admin | mới (bảng `processing_jobs` đã có) | Trang mới, `SystemStatusPage` |
| GET | `/admin/processing-jobs/{id}` | Admin | mới | Trang mới (poll tiến độ) |
| POST | `/admin/processing-jobs/{id}/cancel` | Admin | mới | Trang mới |

- `POST` multipart: `file` (mp4/mkv/avi, giới hạn chốt ở BE-01), `recorded_started_at` (mốc thời gian gốc của video, map vào `timeline_origin_utc`), `sampling_profile` allowlist (`baseline`/`throughput`, tùy chọn). Header `Idempotency-Key` để retry không tạo job trùng. Trả `202` với job và snapshot `sampling_interval` thực tế.
- FE dùng `apiService.upload(..., { onProgress })` sẵn có cho thanh tiến trình upload.
- Job item: `id`, `camera` (`id`, `name`), `source_type` (`FILE`|`RTSP`), `status` (`PENDING`|`RUNNING`|`SUCCEEDED`|`FAILED`|`CANCELLED`), `processed_frames`, `total_frames`, `tracks_ready`, `tracks_failed`, `started_at`, `ended_at`, `error_code`, `error_message`.
- FE poll `GET /admin/processing-jobs/{id}` mỗi 3s khi job `PENDING`/`RUNNING`.
- Lỗi: `413 file_too_large`, `415 unsupported_media`, `409 camera_ai_disabled`, `507 insufficient_storage`.
- Worker chạy tuần tự (concurrency 1), không nằm trong request Flask.

### Phase 5 — Tìm kiếm và media kết quả (BE-14, BE-15, BE-16) · ĐÃ TRIỂN KHAI

Đã có API tìm kiếm ba mode, encoder gateway demo/HTTP, lọc camera theo area, ảnh crop/frame và giao diện Operator dùng dữ liệu thật. Fake encoder chỉ được dùng với config `fake_demo_v1`; model khác gọi `PERSON_SEARCH_ENCODER_URL`. Xem [thiết lập Phase 5](phase-5-setup.md) và [OpenAPI Phase 5](openapi-phase-5.json).

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/me/cameras` | Operator | mới | `SearchForm` chip chọn camera |
| POST | `/searches/image` | Operator | service (`TrackSearchService`) + encoder gateway mới | `SearchPage` chế độ ảnh |
| POST | `/searches/text` | Operator | service + encoder gateway mới | `SearchPage` chế độ văn bản |
| POST | `/searches/attributes` | Operator | service + prompt builder mới | `SearchPage` chế độ thuộc tính |
| GET | `/search-results/{track_id}/crop` | Operator | service (`TrackImageService`) | `ResultCard`, `PersonCrop` |
| GET | `/search-results/{track_id}/frame` | Operator | service (`TrackImageService`) | `ResultViewer`, `SceneFrame` |

- `GET /me/cameras`: camera `ACTIVE` thuộc area hiện tại của Operator; thay `cameras.filter(c => c.area === me.area)` ở `SearchPage`.
- Filter dùng chung ba mode: `camera_ids` (tập con camera trong area, rỗng = tất cả), `appeared_from`, `appeared_to`, `top_k`.
- `/searches/image`: multipart `image` (jpg/png) + các field filter.
- `/searches/text`: JSON `{ "text": "người mặc áo đỏ, quần đen, mang ba lô", "top_k": 8, ... }`.
- `/searches/attributes`: JSON

```json
{
  "attributes": { "upper_color": "red", "lower_color": "black", "upper_type": "t_shirt", "has_backpack": true },
  "top_k": 8,
  "camera_ids": [],
  "appeared_from": "2026-09-22T17:00:00Z",
  "appeared_to": "2026-09-25T16:59:59Z"
}
```

- Response chung:

```json
{
  "mode": "ATTRIBUTES",
  "prompt": "A person wearing a red t-shirt and black pants, carrying a backpack.",
  "encoder_version": "rasa-v1",
  "top_k": 8,
  "results": [
    {
      "track_id": "uuid",
      "matching_score": 0.91,
      "camera": { "id": "uuid", "name": "A-01 Cổng chính" },
      "area": { "id": "uuid", "name": "Gate A" },
      "appeared_at": "2026-09-25T02:12:44Z",
      "bbox": { "x": 120, "y": 80, "width": 96, "height": 260, "frame_width": 1920, "frame_height": 1080 },
      "crop_url": "/api/v1/search-results/uuid/crop",
      "frame_url": "/api/v1/search-results/uuid/frame"
    }
  ]
}
```

- Kết quả sắp theo `matching_score` giảm dần; số lượng có thể ít hơn `top_k`; không có ngưỡng loại.
- `bbox` đổi từ phần trăm (mock hiện tại) sang pixel; `SceneFrame` tính phần trăm bằng `frame_width`/`frame_height`.
- Thuộc tính shirt/pants/bag trong `describeResult` là dữ liệu mock, backend không có. FE bỏ các swatch đó hoặc chỉ hiển thị thuộc tính của truy vấn.
- Lỗi: `403 camera_out_of_scope`, `422 invalid_top_k`, `422 invalid_image`, `422 text_too_short`, `503 encoder_unavailable`, `503 vector_search_unavailable`.
- Media: `image/jpeg`; `404 track_not_found` khi ngoài area; `410 image_unavailable` khi frame mất (FE hiện placeholder "Ảnh không khả dụng", metadata vẫn hiển thị).
- Không ghi audit cho mỗi lượt search.

### Phase 6 — Case của Operator (BE-17) · ĐÃ TRIỂN KHAI

Đã có route `/cases` dùng `CaseService`, ảnh crop/frame của CaseResult và giao diện Operator/Viewer (`CaseBrowserPage`, `CaseDetail`, `AddToCaseDialog`, `CreateCaseDialog`) dùng dữ liệu thật. Migration `20260925_0009` thêm cột `cases.version`; [OpenAPI Phase 6](openapi-phase-6.json).

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/cases` | Operator (Case của mình), Viewer (tất cả) | service | `CaseBrowserPage`, `AddToCaseDialog` |
| POST | `/cases` | Operator | service | `CreateCaseDialog` |
| GET | `/cases/{id}` | Operator owner, Viewer | service | `CaseDetail` |
| PATCH | `/cases/{id}` | Operator owner | service | `CaseDetail` sửa title/note |
| POST | `/cases/{id}/results` | Operator owner | service | `AddToCaseDialog`, `CreateCaseDialog` |
| DELETE | `/cases/{id}/results/{case_result_id}` | Operator owner | service | `CaseDetail` nút xóa |
| GET | `/cases/{id}/results/{case_result_id}/crop` | Operator owner, Viewer | service | `CaseItemGrid` |
| GET | `/cases/{id}/results/{case_result_id}/frame` | Operator owner, Viewer | service | `ResultViewer` trong Case |

- `GET /cases?owner_user_id=&created_from=&created_to=&limit=20&cursor=`. Operator luôn chỉ nhận Case của mình (backend bỏ qua `owner_user_id`); Viewer được lọc theo Operator.
- Case summary: `id`, `title`, `note`, `owner` (`id`, `display_name`, `status`), `result_count`, `created_at`, `updated_at`, `version`. `result_count` cần bổ sung vào `CaseSummary` vì `CaseList` hiển thị "N kết quả".
- `POST /cases`: `{ "title", "note", "track_id" }`; `track_id` tùy chọn để khớp luồng "Tạo Case từ kết quả" trong `CreateCaseDialog` (tạo Case và CaseResult đầu tiên trong một transaction).
- `GET /cases/{id}`: `{ "case": {...}, "results": [{ "id", "case_id", "track_id", "camera_name", "area_name", "appeared_at", "saved_at", "bbox", "crop_url", "frame_url" }] }`. Không có `matching_score`. `bbox` (pixel, cùng dạng Phase 5) lấy từ track để `ResultViewer` vẽ khung; `null` nếu không đọc được.
- `PATCH`: `title`, `note`, `version` (bắt buộc). Gửi `owner_user_id`/`status`/`area_id` trả `422`. Lệch `version` trả `409 version_conflict`. `version` chỉ tăng khi sửa title/note; thêm/xóa kết quả chỉ đổi `updated_at`.
- `POST /cases/{id}/results`: `{ "track_id" }`, trả `201` với CaseResult. Luôn tạo row mới kể cả trùng track. Track ngoài area hiện tại trả `403 track_not_savable`.
- `DELETE` trả `204`, chỉ xóa CaseResult, không xóa track/frame/vector.
- Case của Operator khác, hoặc CaseResult không thuộc Case trên URL, trả `404` (`case_not_found` / `case_result_not_found`). Admin gọi `/cases` trả `403`.
- Bộ lọc Operator phía Viewer lấy từ `GET /viewer/operators` (Phase 7). Bộ lọc ngày lọc theo `created_at`.

### Phase 7 — Viewer (BE-18) · ĐÃ TRIỂN KHAI

Đã có `/viewer/dashboard`, `/viewer/operators`; `OverviewPage` và bộ lọc Operator của `CaseBrowserPage` dùng dữ liệu thật, đã xóa `src/mocks/cases.js`. Không cần migration. [OpenAPI Phase 7](openapi-phase-7.json).

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/viewer/dashboard` | Viewer | service (`viewer_dashboard`) | `OverviewPage` |
| GET | `/viewer/operators` | Viewer | mới | `CaseBrowserPage` filter Operator |

- Dashboard: `{ "total_cases", "total_case_results", "recent_cases": [CaseSummary] }`. `total_case_results` đếm cả CaseResult trùng track. Query `recent_limit` (1–50, mặc định 10; FE gửi 6); `recent_cases` sắp theo `updated_at` giảm dần.
- `/viewer/operators`: danh sách `id`, `display_name`, `status` của mọi Operator từng sở hữu Case, kể cả đã khóa/ngừng hoạt động; thay `users` mock đang dùng để hiển thị tên owner.
- Viewer đọc Case và media qua cùng endpoint Phase 6; mọi request sửa trả `403`.

### Phase 8 — Giám sát: trạng thái, chẩn đoán, audit (BE-11, BE-12, BE-13, BE-22) · ĐÃ TRIỂN KHAI

Đã có `MonitoringService` (trạng thái + chẩn đoán), `AuditLogService` trả `target_label`/`actor` và danh sách actor; `SystemStatusPage`, `DiagnosticsPage`, `AuditLogPage` dùng dữ liệu thật. Không cần migration. [OpenAPI Phase 8](openapi-phase-8.json).

Khác biệt so với thiết kế ban đầu:

- `worker_state` tính từ `processing_jobs`: `DISABLED` khi tắt AI, `RUNNING`/`QUEUED` theo job đang chạy/chờ, `ERROR` khi lease job hết hạn (`worker_heartbeat_lost`) hoặc job cuối cùng `FAILED` (`last_error` = mã stage), còn lại `IDLE`. Chưa có bảng heartbeat riêng của worker.
- `connection` thêm `NOT_CONFIGURED` cho camera chỉ dùng video tải lên (FE hiển thị "Video tải lên", tính là bình thường). Mỗi camera có `category` để FE lọc, `summary` đếm theo `category`.
- `metrics` luôn `null` cho tới khi worker báo số liệu.
- Chẩn đoán pipeline chạy Detector/Tracker/Image Encoder trên khung hình tổng hợp (không dùng ảnh camera thật); nguồn RTSP được kiểm tra bằng `ffprobe` với allowlist mạng. Cấu hình AI không có adapter trên máy chủ trả bước `DETECTOR` `FAILED`.
- Chẩn đoán search kiểm tra cấu hình encoder, Text/Image Encoder và ba kho dữ liệu.
- Bộ lọc audit theo nhóm: FE gửi nhiều `event_type`. Ô tìm kiếm tự do cũ bị bỏ vì backend chưa hỗ trợ.

| Method | Path | Role | BE sẵn có | FE dùng tại |
| --- | --- | --- | --- | --- |
| GET | `/admin/system-status` | Admin | một phần (`StorageStatusService`) | `SystemStatusPage` |
| POST | `/admin/diagnostics/camera-pipeline` | Admin | mới | `DiagnosticsPage` nhóm pipeline |
| POST | `/admin/diagnostics/search-components` | Admin | mới | `DiagnosticsPage` nhóm search |
| GET | `/admin/audit-logs` | Admin | service (`AuditLogService`) | `AuditLogPage` |
| GET | `/admin/audit-logs/actors` | Admin | mới | `AuditLogPage` filter người thực hiện |

`GET /admin/system-status`:

```json
{
  "generated_at": "2026-09-25T02:48:12Z",
  "summary": { "healthy": 6, "connection_issues": 2, "ai_issues": 1, "unknown": 1 },
  "cameras": [
    {
      "id": "uuid",
      "name": "A-03 Hành lang tầng 2",
      "area_name": "Gate A",
      "connection": "ONLINE",
      "ai_enabled": true,
      "worker_state": "ERROR",
      "active_job_id": "uuid",
      "last_heartbeat_at": "2026-09-25T02:15:03Z",
      "last_error": "Tracker: CUDA out of memory",
      "metrics": { "source_fps": 20, "processed_fps": null, "latency_ms": null }
    }
  ],
  "storage": { "postgres": "UP", "milvus": "UP", "minio": "UP" },
  "encoder": "UP",
  "worker": { "state": "IDLE", "queue_depth": 0, "last_heartbeat_at": "..." }
}
```

- `worker_state`: `IDLE` | `QUEUED` | `RUNNING` | `ERROR` | `DISABLED`. FE map sang `AI_STATE` (`running`, `stopped`, `error`, `off`, `unknown`) và `connection` + `status` sang `CAMERA_STATUS` (bảng 4.3).
- FE nút "Làm mới" gọi lại endpoint; hiển thị `generated_at` thay cho `lastUpdated` giả.
- Diagnostics: pipeline nhận `{ "camera_id" }`, search components không nhận body. Response:

```json
{
  "ran_at": "...",
  "overall": "INCONCLUSIVE",
  "steps": [
    { "component": "FRAME_SOURCE", "label": "Nhận khung hình", "outcome": "SUCCESS", "message": "25 frame/s · 1920×1080", "duration_ms": 120 },
    { "component": "DETECTOR", "label": "Detector · YOLOv8-m", "outcome": "INCONCLUSIVE", "message": "Khung hình không có người", "duration_ms": 9 },
    { "component": "TRACKER", "outcome": "SKIPPED" },
    { "component": "IMAGE_ENCODER", "outcome": "SKIPPED" }
  ]
}
```

  Thay `buildDiagnosticPlan` mock; `summarizeDiagnostic` dùng `overall`. Rate limit và timeout; không trả danh sách người tìm thấy.
- Audit: `GET /admin/audit-logs?occurred_from=&occurred_to=&actor_user_id=&event_type=case.created&event_type=auth.login&result=FAILURE&limit=50&cursor=`. Item: `id`, `occurred_at`, `actor` (`id`, `username` hoặc `null` = system), `event_type`, `target_type`, `target_id`, `target_label`, `result`, `metadata`. `target_label` cần thêm (tên camera/username/tiêu đề Case) vì `AuditLogPage` hiển thị cột "Đối tượng".
- Nhóm FE theo `event_type`: `auth.*` → Đăng nhập, `user.*`/`operator.*` → Tài khoản, `camera.*` → Camera, `ai.state_changed` → Xử lý AI, `ai.config_*` → Mô hình AI, `case.*` → Case, `system.*`/`storage.*` → Lỗi hệ thống.

### Phase 9 — Hardening (BE-19 đến BE-25) · ĐÃ TRIỂN KHAI (trừ E2E)

- Rate limit fixed-window trong bộ nhớ mỗi process (`RATE_LIMITS` trong config): login 10/phút theo IP + username, search 30/phút, upload 10/phút, RTSP test 10/phút, diagnostics 6/phút theo người dùng. Vượt ngưỡng trả `429 rate_limited` + `Retry-After`. Chạy nhiều process thì mỗi process đếm riêng.
- Security headers cho mọi response (`nosniff`, `X-Frame-Options: DENY`, CSP `default-src 'none'`, `Referrer-Policy`, `Cache-Control: no-store` cho `/api`, HSTS khi cookie `Secure`).
- CORS allowlist qua `PERSON_SEARCH_CORS_ORIGINS` (danh sách origin, phân tách bằng dấu phẩy; để trống khi dùng proxy Vite).
- FE thêm "Mã tra cứu" (8 ký tự đầu `request_id`) vào thông báo lỗi 5xx.
- Test ma trận quyền tự duyệt mọi route `/api/v1` (route mới chưa khai báo quyền sẽ làm test fail), test CSRF, rate limit, header, CORS.
- Đã có từ trước: chữ ký file upload, chống SSRF RTSP, `Idempotency-Key`, `version`, request ID trong envelope.
- Đã xóa `GET /api/v1/ping` và toàn bộ `frontend/src/mocks`.
- Chưa làm: E2E login → job → search → Case → Viewer (cần stack Docker).

Không thêm endpoint mới. Áp dụng lên mọi endpoint ở trên:

- Rate limit: login, connection test, diagnostics, upload, search.
- `Idempotency-Key` cho upload job; `version` cho user/camera/AI config/Case.
- Request ID trong header `X-Request-ID` và trong error envelope; FE hiển thị kèm toast lỗi để tra log.
- CORS allowlist, security headers, validate chữ ký file upload, chống SSRF cho RTSP test.
- Test ma trận quyền và IDOR cho mọi route; E2E login → job → search → Case → Viewer.

### 4.3 Bảng map trạng thái camera cho FE

| `status` | `rtsp_status` | UI `CAMERA_STATUS` |
| --- | --- | --- |
| `RETIRED` | bất kỳ | `retired` |
| `ACTIVE` | `ONLINE` | `online` |
| `ACTIVE` | `OFFLINE`/`ERROR` | `offline` |
| `ACTIVE` | `UNKNOWN`, chưa từng test thành công | `unverified` |
| `INACTIVE` | bất kỳ | `unknown` |

| `ai_enabled` | `worker_state` | UI `AI_STATE` |
| --- | --- | --- |
| `false` | bất kỳ | `off` |
| `true` | `RUNNING` | `running` |
| `true` | `QUEUED` | `starting` |
| `true` | `IDLE` | `stopped` |
| `true` | `ERROR` | `error` |
| `true` | không có heartbeat | `unknown` |

## 5. Thứ tự triển khai đề xuất

Ưu tiên phase dùng service đã có để FE sớm có dữ liệu thật, trong khi worker/encoder làm song song.

| Mốc | Backend | Frontend | Phụ thuộc |
| --- | --- | --- | --- |
| M0 | BE-01: OpenAPI v1, error envelope, pagination, session/CSRF | Refactor `apiService`, thêm `services/api/*`, `mappers.js`, proxy Vite | — |
| M1 | Phase 1 auth + policy | `LoginPage`, guard, logout qua API | M0 |
| M2 | Phase 2 areas/users | `UsersPage`, `UserDialog` | M1 |
| M3 | Phase 6 + 7 Case và Viewer (service sẵn có) | `CaseBrowserPage`, `CaseDetail`, `OverviewPage`; bỏ `score` khỏi Case (G3) | M1 |
| M4 | Phase 3 camera/AI config | `CamerasPage`, `CameraDialog`, `AiProcessingPage`, `ModelsPage` | M2 |
| M5 | Phase 4 job + worker với fake AI adapter | Trang "Xử lý video" mới | M4 |
| M6 | Phase 5 search + media (fake encoder trước, RaSa sau) | `SearchPage`, `SearchResults`, `ResultViewer`, `AddToCaseDialog`; `top_k` 4/8/12/16 (G2) | M3, M5 |
| M7 | Phase 8 status/diagnostics/audit | `SystemStatusPage`, `DiagnosticsPage`, `AuditLogPage` | M4, M5 |
| M8 | Phase 9 hardening + E2E | Xóa `src/mocks/*`, xử lý lỗi/empty state cuối cùng | Tất cả |

Mỗi mốc xong khi: endpoint có trong OpenAPI, có test route + quyền, màn hình FE tương ứng không còn import từ `src/mocks`.

## 6. Tổng hợp endpoint

| # | Method | Path | Role | Phase |
| --- | --- | --- | --- | --- |
| 1 | POST | `/auth/login` | Public | 1 |
| 2 | GET | `/auth/me` | Đã đăng nhập | 1 |
| 3 | POST | `/auth/logout` | Đã đăng nhập | 1 |
| 4 | GET | `/areas` | Admin, Operator | 2 |
| 5 | GET | `/admin/users` | Admin | 2 |
| 6 | POST | `/admin/users` | Admin | 2 |
| 7 | GET | `/admin/users/{id}` | Admin | 2 |
| 8 | PATCH | `/admin/users/{id}` | Admin | 2 |
| 9 | POST | `/admin/users/{id}/lock` | Admin | 2 |
| 10 | POST | `/admin/users/{id}/unlock` | Admin | 2 |
| 11 | POST | `/admin/users/{id}/deactivate` | Admin | 2 |
| 12 | GET | `/admin/cameras` | Admin | 3 |
| 13 | POST | `/admin/cameras` | Admin | 3 |
| 14 | GET | `/admin/cameras/{id}` | Admin | 3 |
| 15 | PATCH | `/admin/cameras/{id}` | Admin | 3 |
| 16 | POST | `/admin/cameras/{id}/retire` | Admin | 3 |
| 17 | POST | `/admin/cameras/{id}/connection-tests` | Admin | 3 |
| 18 | PUT | `/admin/cameras/{id}/ai-state` | Admin | 3 |
| 19 | GET | `/admin/ai/models` | Admin | 3 |
| 20 | GET | `/admin/ai/config` | Admin | 3 |
| 21 | PUT | `/admin/ai/config` | Admin | 3 |
| 22 | POST | `/admin/cameras/{id}/processing-jobs` | Admin | 4 |
| 23 | GET | `/admin/processing-jobs` | Admin | 4 |
| 24 | GET | `/admin/processing-jobs/{id}` | Admin | 4 |
| 25 | POST | `/admin/processing-jobs/{id}/cancel` | Admin | 4 |
| 26 | GET | `/me/cameras` | Operator | 5 |
| 27 | POST | `/searches/image` | Operator | 5 |
| 28 | POST | `/searches/text` | Operator | 5 |
| 29 | POST | `/searches/attributes` | Operator | 5 |
| 30 | GET | `/search-results/{track_id}/crop` | Operator | 5 |
| 31 | GET | `/search-results/{track_id}/frame` | Operator | 5 |
| 32 | GET | `/cases` | Operator, Viewer | 6 |
| 33 | POST | `/cases` | Operator | 6 |
| 34 | GET | `/cases/{id}` | Operator owner, Viewer | 6 |
| 35 | PATCH | `/cases/{id}` | Operator owner | 6 |
| 36 | POST | `/cases/{id}/results` | Operator owner | 6 |
| 37 | DELETE | `/cases/{id}/results/{case_result_id}` | Operator owner | 6 |
| 38 | GET | `/cases/{id}/results/{case_result_id}/crop` | Operator owner, Viewer | 6 |
| 39 | GET | `/cases/{id}/results/{case_result_id}/frame` | Operator owner, Viewer | 6 |
| 40 | GET | `/viewer/dashboard` | Viewer | 7 |
| 41 | GET | `/viewer/operators` | Viewer | 7 |
| 42 | GET | `/admin/system-status` | Admin | 8 |
| 43 | POST | `/admin/diagnostics/camera-pipeline` | Admin | 8 |
| 44 | POST | `/admin/diagnostics/search-components` | Admin | 8 |
| 45 | GET | `/admin/audit-logs` | Admin | 8 |
| 46 | GET | `/admin/audit-logs/actors` | Admin | 8 |

Health (hạ tầng, đã có): `GET /health/live`, `GET /health/ready`, `GET /health/storage`. `GET /api/v1/ping` đã xóa ở Phase 9.

## 7. Câu hỏi mở cần chốt ở BE-01

- Q1: Session lưu PostgreSQL (mặc định) hay store khác; thời gian hết hạn phiên và idle timeout.
- Q2: Giới hạn kích thước ảnh truy vấn, video upload, độ dài text; timeout encoder và RTSP test.
- Q3: Có thêm mã Case dễ đọc (`CS-0142`) không, hay FE hiển thị UUID rút gọn.
- Q4: Mô tả tiếng Việt ở `/searches/text` được dịch/tiền xử lý thế nào trước RaSa Text Encoder.
- Q5: **Đã chốt Phase 4:** tắt AI/cancel dừng ở checkpoint tiếp theo; ingestion đang chạy có thể hoàn tất, track đã lưu được giữ.
- Q6: **Đã chốt Phase 4:** filesystem private; xóa khi job terminal, dọn file upload mồ côi sau 24 giờ.
- Q7: **Đã chốt Phase 4:** job FAILED cần upload lại với Idempotency-Key mới; crash worker tự replay tối đa 3 lần trước khi FAILED.
- Q8: Tài nguyên tồn tại nhưng không có quyền trả `403` hay `404` (đề xuất `404` cho Case/track/media, `403` cho route sai role).
