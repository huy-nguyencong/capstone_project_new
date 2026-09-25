export const STEP_STATE = {
  SUCCESS: 'ok',
  INCONCLUSIVE: 'warn',
  FAILED: 'fail',
  SKIPPED: 'skip',
}

const STEP_LABEL = {
  FRAME_SOURCE: 'Nguồn khung hình',
  DETECTOR: 'Detector',
  TRACKER: 'Tracker',
  IMAGE_ENCODER: 'Image Encoder',
  TEXT_ENCODER: 'Text Encoder',
  ACTIVE_CONFIG: 'Cấu hình encoder',
}

export const toDiagnosticSteps = (report) =>
  report.steps.map((step) => ({
    name: step.label || STEP_LABEL[step.component] || step.component,
    state: STEP_STATE[step.outcome] ?? 'skip',
    msg: [step.message, step.duration_ms != null ? `${step.duration_ms} ms` : null]
      .filter(Boolean)
      .join(' · '),
  }))

export const summarizeDiagnostic = (report, steps) => {
  if (report.overall === 'FAILED') {
    const failed = steps.filter((s) => s.state === 'fail').map((s) => s.name)
    return { tone: 'err', text: `Phát hiện lỗi tại: ${failed.join(', ')}.` }
  }
  if (report.overall === 'INCONCLUSIVE') {
    return {
      tone: 'warn',
      text: 'Chưa thể xác minh đầy đủ vì dữ liệu kiểm tra không có người — không kết luận pipeline bị lỗi.',
    }
  }
  return { tone: 'ok', text: 'Tất cả thành phần hoạt động bình thường.' }
}
