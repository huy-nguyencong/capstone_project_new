# Truy vấn vector có kiểm tra quyền (STO-13)

Code: `person_search.services.track_search.TrackSearchService.search(actor_user_id, query)`.

## Luồng

1. `top_k` phải thuộc `{4, 8, 12, 16}`; `bool` bị từ chối.
2. Đọc User từ PostgreSQL theo `actor_user_id`. Chỉ Operator `ACTIVE` có `assigned_area_id`
   được tìm kiếm. Area luôn lấy từ PostgreSQL; query không có trường area.
3. Mỗi camera filter phải tồn tại và thuộc area hiện tại, nếu không thì cả request bị từ chối
   (`CameraOutOfScopeError`) trước khi gọi Milvus.
4. Milvus nhận filter area, danh sách camera (`camera_id in [...]`) và khoảng thời gian trước
   khi chọn `top_k`.
5. Hydrate hit từ PostgreSQL (track + camera + area). Chỉ giữ hit mà track `READY`, camera thuộc
   area hiện tại, khớp camera/time filter. Hit không đạt (stale, thiếu, `PENDING`, `FAILED`,
   khác area) bị bỏ, cộng vào `SearchMetrics.stale_hits` và log cảnh báo.
6. Response `TrackSearchResult` chứa `matching_score` tạm thời; score không được ghi xuống
   PostgreSQL. Thứ tự giữ nguyên thứ tự Milvus. Có thể trả ít hơn `top_k`.

## Policy đã chốt

- Track của camera `INACTIVE`/`RETIRED` vẫn tìm được nếu camera thuộc area hiện tại: ngừng camera
  chỉ dừng tạo track mới, không xóa lịch sử.
- Operator bị đổi area chỉ tìm được trong area mới.

## Lỗi

| Exception | Ý nghĩa |
| --- | --- |
| `InvalidSearchRequestError` | `top_k` sai, time filter không có timezone hoặc đảo ngược, embedding sai. |
| `SearchNotAllowedError` | Actor không phải Operator `ACTIVE` có area. |
| `CameraOutOfScopeError` | Camera filter không tồn tại hoặc ngoài area. |
