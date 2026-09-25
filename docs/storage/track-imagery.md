# Ảnh track có kiểm tra quyền (STO-14)

Code: `person_search.services.track_imagery.TrackImageService`.

## Hai context quyền

| Method | Ai được xem | Điều kiện |
| --- | --- | --- |
| `search_result_image(actor, track_id, variant)` | Operator `ACTIVE` | Track `READY`, camera thuộc area hiện tại của Operator. |
| `case_result_image(actor, case_result_id, variant)` | Operator `ACTIVE` sở hữu Case; Viewer `ACTIVE` | `CaseResult` tồn tại. Không phụ thuộc area hiện tại nên Operator đổi area vẫn xem ảnh trong Case cũ. |

Không lưu phiên tìm kiếm (theo `architect.md` không dùng `result_ref`), nên context tìm kiếm
dùng đúng điều kiện của STO-13. API không nhận object key; object key luôn lấy từ PostgreSQL.

- Admin, user không `ACTIVE`, hoặc Viewer gọi ảnh tìm kiếm: `ImageAccessDeniedError` (403).
- Track/CaseResult không tồn tại hoặc actor không có quyền trên đúng đối tượng đó:
  `TrackImageNotFoundError` (404) để không lộ sự tồn tại.

## Render

- `PERSON_CROP`: crop động theo bbox, có `crop_padding_ratio` (mặc định 0), clamp vào biên ảnh.
- `FULL_FRAME`: full frame có viền đỏ quanh bbox.
- Downscale theo `max_edge` (mặc định 1920), encode JPEG; nếu vượt `max_output_bytes`
  (mặc định 5 MiB) thì giảm quality 70 rồi 50, vẫn vượt thì báo lỗi.
- Response: `image/jpeg`, `Cache-Control: private, no-store`.
- Không ghi crop hay preview vào MinIO hoặc đĩa.

## Ảnh thiếu hoặc hỏng

`TrackImageUnavailableError(track_id, reason)`, không xóa hay ẩn CaseResult:

| `reason` | Nguyên nhân |
| --- | --- |
| `FRAME_MISSING` | Object không có trên MinIO hoặc track không có object key. |
| `FRAME_CORRUPT` | Checksum sai, không decode được, hoặc kích thước khác metadata track. |
| `BBOX_INVALID` | Bbox sau khi clamp không còn diện tích. |
| `RESPONSE_TOO_LARGE` | Ảnh sau nén vẫn vượt giới hạn. |

Lỗi hạ tầng MinIO khác (timeout, mất kết nối) được ném nguyên để tầng API trả 503.
