import { detectorName, trackerName } from '@/mocks/models'

const SKIP_FRAME = 'Bỏ qua vì phụ thuộc frame'

export const buildDiagnosticPlan = (group, camera, models) => {
  if (group === 'search') {
    return [
      {
        name: 'Image Encoder · CLIP ViT-B/16',
        out: 'ok',
        msg: 'Ảnh kiểm tra → embedding 512 chiều · 14 ms',
      },
      {
        name: 'Text Encoder · CLIP ViT-B/16',
        out: 'ok',
        msg: 'Câu kiểm tra → embedding 512 chiều · 6 ms',
      },
    ]
  }

  const names = [
    'Nhận khung hình RTSP',
    `Detector · ${detectorName(models.det)}`,
    `Tracker · ${trackerName(models.trk)}`,
    'Image Encoder',
  ]

  let outcomes
  if (!camera || camera.status !== 'online') {
    outcomes = [
      ['fail', 'Không nhận được frame từ RTSP — lỗi nguồn dữ liệu'],
      ['skip', SKIP_FRAME],
      ['skip', SKIP_FRAME],
      ['skip', SKIP_FRAME],
    ]
  } else if (camera.aiState === 'error') {
    outcomes = [
      ['ok', 'Nhận 20 frame/s · 1280×720'],
      ['ok', 'Phát hiện 2 người · 10 ms'],
      ['fail', 'Không khởi tạo được Tracker: CUDA out of memory'],
      ['skip', 'Bỏ qua vì Tracker lỗi'],
    ]
  } else if (camera.id === 'c2') {
    outcomes = [
      ['ok', 'Nhận 25 frame/s · 1920×1080'],
      ['warn', 'Khung hình hiện tại không có người'],
      ['warn', 'Chưa có track để xác minh'],
      ['warn', 'Chưa có vùng người để mã hóa'],
    ]
  } else {
    outcomes = [
      ['ok', `Nhận ${camera.fps || 25} frame/s · ${camera.res.split(' · ')[0]}`],
      ['ok', 'Phát hiện 3 người · 9 ms'],
      ['ok', 'Duy trì 3 track · 2 ms'],
      ['ok', 'Sinh 3 Person Embedding · 512 chiều'],
    ]
  }

  return names.map((name, i) => ({ name, out: outcomes[i][0], msg: outcomes[i][1] }))
}

export const summarizeDiagnostic = (plan) => {
  const failed = plan.filter((p) => p.out === 'fail')
  if (failed.length) {
    return { tone: 'err', text: `Phát hiện lỗi tại: ${failed.map((p) => p.name).join(', ')}.` }
  }
  if (plan.some((p) => p.out === 'warn')) {
    return {
      tone: 'warn',
      text: 'Chưa thể xác minh đầy đủ vì khung hình không có người — không kết luận pipeline bị lỗi.',
    }
  }
  return { tone: 'ok', text: 'Tất cả thành phần hoạt động bình thường.' }
}
