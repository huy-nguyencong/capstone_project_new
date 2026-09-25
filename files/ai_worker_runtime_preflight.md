# AI worker runtime/device preflight

> Task: AIW-04  
> Trạng thái: `REVIEW` sau khi code, tests và local report đạt

## 1. Readiness gate

Worker chạy preflight trước khi kết nối storage hoặc claim job. Gate kiểm tra:

- Python runtime và package inventory có checksum tái lập;
- RAM khả dụng và disk trống theo profile;
- PyAV có decoder H.264/MPEG-4 và có cả `ffmpeg`/`ffprobe` CLI;
- CPU, display adapter/iGPU, PyTorch, CUDA, GPU name và output `nvidia-smi`;
- artifact/checksum/license từ registry, device support và package của từng adapter;
- model-load probe cùng RAM process trước/sau khi nạp model;
- ít nhất một bộ Detector/Tracker/Encoder tương thích thực sự đạt.

Report không chứa credential, raw frame hoặc embedding. Worker dừng bằng danh sách code thành phần như `ram_below_threshold`, `codec_unavailable`, `cuda_unavailable` hoặc `pipeline_models_unavailable`; không nhận job rồi mới crash/OOM.

## 2. Resource profiles đã khóa

| Giá trị | `local_cpu` | `colab_t4` |
| --- | ---: | ---: |
| Device | CPU | CUDA bắt buộc |
| RAM trống tối thiểu | 4 GiB | 8 GiB |
| Disk trống tối thiểu | 5 GiB | 10 GiB |
| Worker threads | 2 | 2 |
| Decode threads | 1 | 1 |
| Batch size | 1 | 1 |
| Frame queue | 4 | 4 |
| Active tracks tối đa | 256 | 256 |
| Candidate/full frame mỗi track | tối đa 3 | tối đa 3 |
| Inference timeout | 120 giây | 180 giây |

`batch_size` khác `1`, candidate vượt `3`, thread/buffer vượt giới hạn an toàn hoặc unknown config field đều fail-fast. OpenVINO/DirectML chỉ được ghi nhận là hướng tối ưu; iGPU không được tự động chọn trước khi baseline và benchmark đạt.

## 3. Baseline local ngày 2026-09-26

Report: `files/ai_worker_preflight_local.json`.

- Python 3.12.10, PyAV 16.1.0; decoder H.264 và MPEG-4 có sẵn.
- Khoảng 52,5 GiB disk trống tại thời điểm đo: đạt ngưỡng.
- RAM trống khoảng 4,25 GiB tại lần report cuối: đạt ngưỡng 4 GiB, nhưng đã có lần đo ngay trước đó thấp hơn ngưỡng nên cần giải phóng RAM trước demo.
- Không tìm thấy `ffmpeg`/`ffprobe` CLI: chưa đạt codec gate.
- Không có PyTorch, CUDA hay `nvidia-smi`; demo adapter không cần PyTorch nhưng production không thể đạt.
- Ba demo artifact/model ID đạt checksum. Đây không phải bằng chứng model AI production.

Không hạ ngưỡng chỉ để đổi report sang màu xanh. Trước khi chạy demo worker local cần giữ đủ RAM trống và cài FFmpeg/ffprobe vào `PATH`, sau đó chạy lại cùng lệnh.

## 4. Colab T4 compatibility spike

Notebook `notebooks/ai_worker_colab_preflight.ipynb` dùng profile `colab_t4`, ghi package lock, CUDA/GPU, `nvidia-smi` và report JSON. Setup có thể chạy lại sau runtime reset và không tự tải checkpoint từ URL request.

RaSa upstream công bố stack cũ: PyTorch 1.9.1, torchvision 0.10.1, Transformers 4.8.1 và timm 0.4.9. Preflight so sánh stack thực tế nhưng không ép cài các bản cũ vào Colab Latest. Khác version là cảnh báo; chỉ model-load + inference smoke với checkpoint thật ở AIW-13/AIW-14 mới được phép cấp `model_ready`.

## 5. Lệnh tái lập

Từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe tools\ai_preflight.py `
  --registry config\models.demo.json `
  --resource-config config\ai_resources.json `
  --profile local_cpu `
  --allow-demo `
  --allow-not-ready `
  --output ..\files\ai_worker_preflight_local.json
```

Bỏ `--allow-not-ready` trong readiness gate/CI; khi có bất kỳ failure nào CLI trả exit code `2`.
