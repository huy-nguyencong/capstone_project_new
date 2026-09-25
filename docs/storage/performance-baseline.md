# Baseline hiệu năng và dung lượng (STO-18)

> **Trạng thái:** tool đo đã có, **chưa có số đo**. Các bảng dưới đây phải được điền bằng kết quả
> chạy trên máy demo (Intel Core i5-11300H, 16 GB RAM, Windows, Docker Desktop). Không dùng số ước
> lượng thay cho số đo.

## Công cụ

`backend/tools/storage_benchmark.py` tạo dữ liệu tổng hợp, chạy qua đúng service của ứng dụng rồi
tự dọn dữ liệu (trừ khi `--keep-data`). Nó không downgrade database nhưng ghi thêm rồi xóa các
row có mã `BENCH-*`, nên vẫn nên chạy trên database dev.

- 7 camera chia 2 area (4 + 3), mô phỏng 7 video.
- Frame JPEG tổng hợp (mặc định 1280×720, quality 85, khoảng 160 KB), bbox ngẫu nhiên.
- Vector ngẫu nhiên chuẩn hóa L2, dimension mặc định 256, seed cố định để lặp lại được.
- Đo:
  - ingestion: throughput và p50/p95/p99 qua `TrackIngestionService`;
  - search: latency Milvus thuần và latency service (gồm hydrate PostgreSQL), recall@k so với
    brute-force chính xác, cho từng giá trị `ef`;
  - ảnh: latency crop và full frame qua `TrackImageService`;
  - dung lượng: frame trung bình, row `person_tracks`, payload outbox, vector thô, kích thước bảng
    PostgreSQL, stats collection Milvus;
  - `--docker-stats`: RAM/CPU container lúc idle và sau ingest.

```sh
cd backend
.venv/bin/python tools/storage_benchmark.py --tracks 1000 --queries 200 --docker-stats \
  --tracks-per-video 1500 --output ../docs/storage/benchmarks/demo-1000.json
```

Chạy lần lượt các mốc 1.000 / 5.000 / 10.000 track (hoặc mốc gần số track thật của 7 video sau
khi có số liệu từ AI pipeline). Dùng `--ef 32,64,128,256` để so tham số search; `--ingest-concurrency`
và `--search-concurrency` để thử tải đồng thời.

## Kết quả (điền sau khi đo)

| Mốc | Ingest track/s | Ingest p95 | Search p50/p95 (service) | Recall@16 (ef=64) | Crop p95 | RAM Milvus sau ingest |
| --- | --- | --- | --- | --- | --- | --- |
| 1.000 | chưa đo | | | | | |
| 5.000 | chưa đo | | | | | |
| 10.000 | chưa đo | | | | | |

| Dung lượng mỗi track | Giá trị |
| --- | --- |
| Full frame trung bình | chưa đo |
| Row `person_tracks` | chưa đo |
| Payload outbox (có embedding) | chưa đo |
| Vector thô (256 × 4 byte) | 1.024 byte |

Ước lượng dung lượng cho 7 video:
`số track × (frame + row track + payload outbox + vector) + index HNSW + WAL/overhead`.
Tool in `capacity_projection` khi có `--tracks-per-video`.

## Ngưỡng chấp nhận

Theo plan, ngưỡng được chốt **sau baseline đầu tiên**. Điều kiện tối thiểu:

- Không container nào bị OOM hoặc restart trong suốt lần chạy mốc lớn nhất.
- Search p95 ổn định giữa các lần chạy lặp lại (chênh lệch nhỏ, không tăng dần).
- Dung lượng dự kiến cho 7 video nhỏ hơn dung lượng đĩa còn trống (khoảng 90 GB) sau khi trừ
  Docker image và backup.

Nếu không đạt: ghi ADR điều chỉnh (ví dụ đổi `ef`, giảm kích thước frame, đổi index) thay vì tối
ưu khi chưa có số đo.

## Cách ghi kết quả

Lưu JSON vào `docs/storage/benchmarks/` (file này không chứa dữ liệu nhạy cảm), rồi chép các số
chính vào bảng trên cùng cấu hình máy, phiên bản image và commit SHA.
