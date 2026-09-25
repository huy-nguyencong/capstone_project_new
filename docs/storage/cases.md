# Case, CaseResult và dashboard Viewer (STO-15)

Code: `person_search.services.cases.CaseService`.

## Quyền

| Thao tác | Operator | Viewer | Admin |
| --- | --- | --- | --- |
| `create_case`, `update_case`, `add_result`, `remove_result` | Chỉ Case mình sở hữu | Không | Không |
| `list_cases`, `get_case` | Case mình sở hữu, kể cả sau khi đổi area | Mọi Case, chỉ đọc | Không |
| `viewer_dashboard` | Không | Có | Không |

- Actor luôn được đọc lại từ PostgreSQL và phải `ACTIVE`. Owner lấy từ actor
  (`owner_id_from_authenticated_actor`), không nhận từ client.
- Case của Operator khác trả `CaseNotFoundError` (404) để không lộ sự tồn tại; sai vai trò trả
  `CaseAccessDeniedError` (403). Mutation bị từ chối được ghi audit `FAILURE` qua
  `AuditRecorder.record_standalone`.
- Operator bị khóa không thao tác được, nhưng Case của họ vẫn còn và Viewer vẫn xem được.

## Lưu track vào Case

- `add_result` (và `create_case(..., track_id=...)`) chỉ nhận track `READY` có camera thuộc area
  hiện tại của Operator tại thời điểm lưu; nếu không thì `TrackNotSavableError`.
- Snapshot `camera_name`, `area_name`, `appeared_at` lấy từ PostgreSQL phía server.
- Mỗi lần lưu tạo một `CaseResult` mới, không deduplicate. Không có Matching Score.
- `remove_result` xóa đúng một `case_result_id` thuộc Case đó; không xóa track, frame, vector hay
  mục trùng khác.
- Thêm/xóa mục cập nhật `cases.updated_at` để dashboard phản ánh hoạt động gần nhất.
- `create_case` kèm track chạy trong một transaction: track không hợp lệ thì Case cũng không
  được tạo.

## Sửa Case

`update_case` nhận `title` và/hoặc `note`, khóa dòng Case (`FOR UPDATE`) và so
`expected_updated_at` nếu có để phát hiện ghi đè (`ConcurrentUpdateError`). Audit chỉ ghi tên
field đã đổi, không ghi nội dung title/note.

## Danh sách và dashboard

- `list_cases` sắp xếp `created_at DESC, id DESC`, cursor keyset base64, tối đa 100/trang, lọc
  theo khoảng `created_at`; Viewer lọc thêm theo owner. Owner filter của Operator bị bỏ qua.
- `viewer_dashboard` trả tổng số Case, tổng số row `CaseResult` (tính cả mục lặp cùng track) và
  các Case cập nhật gần nhất kèm tên hiển thị của Operator phụ trách.
