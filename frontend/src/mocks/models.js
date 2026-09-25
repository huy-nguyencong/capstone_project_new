export const DETECTORS = [
  {
    id: 'yolov8m',
    name: 'YOLOv8-m',
    desc: 'Cân bằng tốc độ và độ chính xác',
    meta: '640 px · ~9 ms/frame',
    ready: true,
  },
  {
    id: 'yolov8x',
    name: 'YOLOv8-x',
    desc: 'Độ chính xác cao, tốn GPU hơn',
    meta: '640 px · ~21 ms/frame',
    ready: true,
  },
  {
    id: 'rtdetr',
    name: 'RT-DETR-L',
    desc: 'Transformer, ổn định với đám đông',
    meta: '640 px · ~17 ms/frame',
    ready: true,
  },
  {
    id: 'yolox',
    name: 'YOLOX-s',
    desc: 'Nhẹ, cho thiết bị biên',
    meta: 'Không tải được trọng số mô hình',
    ready: false,
  },
]

export const TRACKERS = [
  {
    id: 'bytetrack',
    name: 'ByteTrack',
    desc: 'Ghép track theo IoU, nhanh',
    meta: 'Không cần đặc trưng ngoại hình',
  },
  { id: 'botsort', name: 'BoT-SORT', desc: 'Có bù chuyển động camera', meta: 'GMC + IoU' },
  {
    id: 'deepsort',
    name: 'DeepSORT',
    desc: 'Ghép track theo đặc trưng ngoại hình',
    meta: 'Yêu cầu đầu ra Detector tương thích',
  },
]

export const FIXED_ENCODERS = [
  { name: 'Image Encoder', role: 'Person Embedding & Query Embedding', model: 'CLIP ViT-B/16' },
  { name: 'Text Encoder', role: 'Mô tả văn bản & bộ lọc thuộc tính', model: 'CLIP ViT-B/16' },
]

export const INCOMPATIBLE = {
  'rtdetr|deepsort': 'RT-DETR-L không xuất đặc trưng ReID mà DeepSORT yêu cầu.',
}

export const detectorName = (id) => DETECTORS.find((d) => d.id === id)?.name ?? id

export const trackerName = (id) => TRACKERS.find((t) => t.id === id)?.name ?? id
