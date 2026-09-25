# AI model registry

> Task: AIW-03  
> Trạng thái: `REVIEW` sau khi schema, loader và tests đạt

## 1. Quyết định triển khai

Registry là allowlist do developer/deployment quản lý, không phải model store và không phải chức năng upload. Manifest chỉ tham chiếu artifact local bằng relative path + SHA-256. Loader tuyệt đối không tải `weights_url`; URL chỉ dùng để ghi provenance.

Production và demo dùng manifest tách biệt:

- `backend/config/models.example.json`: production candidate, không chứa artifact lớn hoặc secret.
- `backend/config/models.demo.json`: synthetic adapters, chỉ được nạp khi `allow_demo=True` hoặc `PERSON_SEARCH_ALLOW_DEMO_MODELS=1`.
- Adapter demo bị loại khỏi allowlist production; production không fallback sang synthetic adapter.

Trường `available` không hợp lệ trong manifest. Loader tự tính trạng thái từ bốn điều kiện:

1. artifact tồn tại bên trong `artifact_root`;
2. SHA-256 trùng manifest;
3. provenance/license đã có `approved_for_project=true`;
4. production entry có ID trong kết quả runtime preflight của server.

Checksum được kiểm lại khi resolve cấu hình, không chỉ lúc đọc manifest, để artifact bị thay đổi sau startup cũng bị từ chối trước khi adapter nạp model.

AIW-04 sẽ tạo bằng chứng runtime/device và truyền tập ID đã qua preflight. Khi chưa có bằng chứng, production candidate vẫn hiển thị nhưng luôn `available=false`.

## 2. Schema đã khóa

Mọi entry có ID ổn định, display name, version pin, adapter kind, artifact local, checksum, device support, input shape và provenance. Ngoài ra:

- Detector có `person_class_id` và `preprocessing_version`.
- Tracker có `compatible_detectors` tham chiếu ID tồn tại.
- Encoder có dimension `256`, L2 normalization và preprocessing version.
- ID là duy nhất toàn registry; unknown field và adapter ngoài allowlist làm startup fail-fast.
- Absolute path, `..`, backslash và URL trong artifact path đều bị từ chối.

API cấu hình chỉ nhận đúng `detector_id`, `tracker_id`, `version`. `model_url`, `artifact_path`, `adapter_class` hoặc bất kỳ field bổ sung nào đều bị từ chối. Khi worker resolve cấu hình đã lưu, version, encoder dimension và checkpoint checksum phải tiếp tục khớp registry hiện tại.

## 3. Candidate production

| Vai trò | Candidate | Adapter | License/provenance gate |
| --- | --- | --- | --- |
| Detector baseline | YOLO nano/small | `ultralytics_yolo` | Chưa approve; cần xác nhận tuân thủ AGPL-3.0 hoặc Enterprise license. |
| Detector dự phòng | YOLOX-Tiny/YOLOX-S | `yolox` | Source Apache-2.0; vẫn phải pin và xác nhận checkpoint cụ thể. |
| Tracker baseline | ByteTrack | `bytetrack` | Source MIT; cần pin commit/config. |
| Tracker thay thế | BoT-SORT | `botsort` | Source MIT; ReID và CMC mặc định tắt theo kế hoạch. |
| Encoder cố định | RaSa CUHK-PEDES | `rasa` | License upstream/checkpoint chưa rõ, giữ `approved=false`. |

Đây là metadata kỹ thuật, không phải kết luận pháp lý. Nguồn đối chiếu: repository/license chính thức của [Ultralytics](https://github.com/ultralytics/ultralytics/blob/main/LICENSE), [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE), [ByteTrack](https://github.com/FoundationVision/ByteTrack/blob/main/LICENSE), [BoT-SORT](https://github.com/NirAharon/BoT-SORT/blob/main/LICENSE) và [RaSa](https://github.com/Flame-Chasers/RaSa).

## 4. Lệnh kiểm tra

Từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe tools\model_registry.py `
  --manifest config\models.demo.json `
  --allow-demo

.\.venv\Scripts\python.exe tools\model_registry.py `
  --manifest config\models.example.json
```

Demo phải báo đủ ba component `available=true`. Production sample phải validate thành công nhưng chưa component nào được nhận là available trước AIW-04 và trước khi thay checksum placeholder bằng checksum artifact thật.
