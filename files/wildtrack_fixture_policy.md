# WILDTRACK — Inventory, fixture policy và quy tắc đánh giá

> Task: AIW-01  
> Dataset root local: `wildtrack-dataset/`  
> Manifest: `files/wildtrack_dataset_manifest.json`  
> Evaluation query set: `files/wildtrack_evaluation_queries.json`

## 1. Inventory đã xác minh

| Hạng mục | Giá trị |
| --- | --- |
| Tổng số file | 3.236 |
| Tổng dung lượng | 11.640.459.534 byte, khoảng 10,84 GiB |
| Video | `cam1.mp4` đến `cam7.mp4` |
| Video format | H.264 trong MP4, 1920×1080, khoảng 59,94 FPS |
| Thời lượng | Khoảng 2.100 giây/video, tương đương 35 phút |
| Số frame khai báo | 125.874 frame ở 6 video; `cam3.mp4` có 125.873 frame |
| Image subsets | 401 PNG RGB 1920×1080 cho mỗi `C1` đến `C7`, tổng 2.807 ảnh |
| Annotation | 400 JSON, frame index 0 đến 1995 với bước 5 |
| Ground-truth identities | 313 `personID` |
| Person-frame rows | 9.518 |
| Bounding boxes hoàn toàn trong frame | 35.084 |
| Bounding boxes cần clamp/cắt theo biên | 7.637 |
| View không nhìn thấy người (`-1`) | 23.905 |
| Calibration | 21 XML: 7 extrinsic, 7 intrinsic original, 7 intrinsic zero |

`viewNum=0..6` ánh xạ sang `C1..C7`. Việc đối chiếu frame đầu video với `00000000.png` bằng mean absolute pixel difference ở kích thước 160×90 cho thấy `cam1→C1`, ..., `cam7→C7` đều là cặp có sai khác thấp nhất rõ ràng. Mapping này được dùng cho inventory; evaluator vẫn phải dùng manifest/checksum để ngăn trộn phiên bản dữ liệu.

## 2. Nguồn và giới hạn sử dụng

- Nguồn chính thức: [EPFL CVLab — The WILDTRACK Seven-Camera HD Dataset](https://www.epfl.ch/labs/cvlab/data/data-wildtrack/).
- Công bố cần trích dẫn: Chavdarova et al., “WILDTRACK: A Multi-camera HD Dataset for Dense Unscripted Pedestrian Detection”, CVPR 2018, DOI `10.1109/CVPR.2018.00528`.
- Trang chính thức xác nhận bảy camera tĩnh, video 1920×1080 ở 60 FPS và 400 frame ground truth ở 2 FPS.
- Bản dữ liệu local không có `LICENSE`, `TERMS` hoặc `README` đi kèm. Trang WILDTRACK chính thức được kiểm tra cũng không nêu một giấy phép phân phối lại rõ ràng. Vì vậy project chỉ coi đây là dữ liệu nghiên cứu dùng local; không commit, đóng gói release hoặc upload công khai dữ liệu/crop cho tới khi quyền phân phối được xác nhận.
- Dữ liệu chứa người thật ở không gian công cộng. Không đưa raw frame, person crop, query image hoặc embedding vào log, issue công khai hay artifact CI.

## 3. Chính sách lưu trữ và versioning

1. `wildtrack-dataset/` phải nằm trong `.gitignore`; không dùng `git add -f`.
2. Git chỉ lưu script inventory, manifest checksum, fixture policy và query metadata dạng text.
3. Không dùng Git LFS mặc định. Chỉ dùng nếu người thực hiện xác nhận quyền phân phối và repository quota.
4. Colab nhận dataset qua storage cá nhân/private hoặc upload có kiểm soát; không nhúng credential database/MinIO/Milvus vào notebook.
5. Mọi benchmark phải ghi `content.tree_sha256`, model/config/checkpoint lineage và sampling interval.

Dataset tree hiện tại:

```text
ecdd328ca203770a143b951b56253e851cbfda4fb19b9b432e73d615f2b5a8f0
```

## 4. Các tầng fixture

### Tier 0 — Unit fixture tổng hợp

- Ảnh/video được sinh trong test hoặc in-memory.
- Không chứa frame WILDTRACK.
- Dùng cho contract, bbox, sampling, selector, state machine và failure injection.
- Chạy mặc định trong `pytest -m unit` và CI.

### Tier 1 — Local integration fixture

- Được tạo cục bộ từ một đoạn ngắn hoặc một số frame WILDTRACK theo script; output nằm trong thư mục ignored/temp.
- Không commit binary fixture trước khi quyền phân phối được xác nhận.
- Dùng để smoke Decoder → Detector → Tracker → Selector → Encoder.
- Phải ghi source camera, source frame/time range và dataset tree checksum.
- Cleanup sau test; person crop chỉ tồn tại trong memory hoặc temp scope của test.

### Tier 2 — Full evaluation dataset

- Dùng đủ 7 video tuần tự, worker concurrency `1`.
- Chỉ chạy khi marker/env flag rõ ràng; không thuộc unit test.
- Output là report/result bundle đã loại secret và không chứa crop lâu dài.
- Kết quả không được gọi là production-quality nếu chưa qua review query labels và ngưỡng chấp nhận.

## 5. Ground truth và quy tắc bbox

- `personID` chỉ là ground truth offline của WILDTRACK. Không persist nó thành danh tính nghiệp vụ và không dùng để merge track xuyên camera trong ứng dụng.
- `viewNum` là 0-based; ánh xạ `0→C1`, ..., `6→C7`.
- Bounding box annotation dùng `xmin`, `ymin`, `xmax`, `ymax`. Evaluator phải clamp về kích thước 1920×1080 trước khi crop hoặc tính metric.
- Bbox có cả bốn giá trị `-1` nghĩa là người không nhìn thấy trong view đó.
- Có 7.637 bbox giao với frame nhưng vượt biên. Đây là `clip_required`, không phải annotation hỏng; selector có thể loại trường hợp clipping nghiêm trọng theo policy best-shot.
- Ảnh `00002000.png` tồn tại ở mỗi camera nhưng annotation cuối là `00001995.json`; không tự tạo ground truth cho frame 2000.
- Video raw dài khoảng 35 phút trong khi annotation/image subset chỉ phủ tập frame được công bố. Trước khi dùng annotation để chấm trực tiếp output video, AIW-26 phải xác minh phép ánh xạ source frame/time chính xác thay vì suy ra chỉ từ tên file.

## 6. Evaluation query set

`wildtrack_evaluation_queries.json` chứa sáu identity có thời lượng xuất hiện và độ phủ camera tốt, với:

- một image query tham chiếu tới full frame+bbox hợp lệ;
- một câu text query tiếng Anh được gán nhãn thủ công;
- một attribute query chỉ dùng schema tiếng Anh hiện có;
- `personID` dùng duy nhất cho phép chấm offline;
- quy tắc loại chính observation dùng làm query để tránh self-match tầm thường.

Text/attribute label là baseline thủ công, không phải annotation chính thức của WILDTRACK. Trước AIW-26 cần có người review lại màu sắc/trang phục trên ít nhất hai camera cho mỗi identity. Nếu appearance thay đổi do góc nhìn/ánh sáng, query vẫn giữ mô tả quan sát được ở query image và báo riêng failure case.

## 7. Lệnh tái lập

Từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe tools\wildtrack_manifest.py generate `
  --dataset-root ..\wildtrack-dataset `
  --output ..\files\wildtrack_dataset_manifest.json

.\.venv\Scripts\python.exe tools\wildtrack_manifest.py verify `
  --dataset-root ..\wildtrack-dataset `
  --manifest ..\files\wildtrack_dataset_manifest.json

.\.venv\Scripts\python.exe tools\wildtrack_manifest.py validate-queries `
  --dataset-root ..\wildtrack-dataset `
  --queries ..\files\wildtrack_evaluation_queries.json
```

`verify` và `validate-queries` phải kết thúc exit code `0`. Nếu có file thiếu, file lạ, sai size, sai SHA-256, sai metadata video, manifest bị sửa không đồng bộ hoặc query không khớp ảnh/annotation, lệnh phải trả exit code `1` và liệt kê lỗi.

## 8. Điều kiện trước AIW-26

- Review thủ công sáu query label trên nhiều view.
- Xác minh mapping giữa raw video timestamp/frame index và image subset/annotation.
- Khóa metric detection/tracking/retrieval và quy tắc xử lý bbox clipping.
- Ghi rõ split/query set version; không tune model trên cùng toàn bộ query dùng báo cáo cuối.
- Không dùng `personID` để thay thế output Tracker hoặc làm rò ground truth vào pipeline production.
