export const TONE = {
  ok: 'var(--color-ok)',
  warn: 'var(--color-warn)',
  err: 'var(--color-danger)',
  mute: 'var(--color-mute)',
  acc: 'var(--color-accent)',
}

export const CAMERA_STATUS = {
  online: { label: 'Trực tuyến', tone: 'ok' },
  offline: { label: 'Mất kết nối', tone: 'err' },
  unverified: { label: 'Chưa xác minh', tone: 'warn' },
  unknown: { label: 'Không xác định', tone: 'mute' },
  retired: { label: 'Ngừng vận hành', tone: 'mute' },
}

export const AI_STATE = {
  running: { label: 'Đang xử lý', tone: 'ok' },
  starting: { label: 'Đang khởi động', tone: 'warn' },
  stopped: { label: 'Ngừng xử lý', tone: 'warn' },
  error: { label: 'Lỗi tiến trình', tone: 'err' },
  off: { label: 'Đã tắt', tone: 'mute' },
  unknown: { label: 'Không xác định', tone: 'mute' },
}

export const USER_STATUS = {
  active: { label: 'Hoạt động', tone: 'ok' },
  locked: { label: 'Đã khóa', tone: 'err' },
  inactive: { label: 'Ngừng hoạt động', tone: 'mute' },
}

export const ROLE_LABEL = {
  admin: 'Admin',
  operator: 'Operator',
  viewer: 'Viewer',
}

export const ROLE_TAG = {
  admin: 'outline',
  operator: 'accent',
  viewer: 'neutral',
}

export const COLORS = {
  red: { label: 'Đỏ', swatch: 'oklch(0.58 0.16 25)' },
  blue: { label: 'Xanh dương', swatch: 'oklch(0.55 0.12 250)' },
  white: { label: 'Trắng', swatch: 'oklch(0.9 0.01 260)' },
  black: { label: 'Đen', swatch: 'oklch(0.3 0.01 260)' },
  green: { label: 'Xanh lá', swatch: 'oklch(0.58 0.1 150)' },
  yellow: { label: 'Vàng', swatch: 'oklch(0.82 0.13 90)' },
  gray: { label: 'Xám', swatch: 'oklch(0.62 0.01 260)' },
  beige: { label: 'Be', swatch: 'oklch(0.78 0.04 70)' },
}

export const PANTS_COLORS = ['black', 'blue', 'gray', 'beige']

export const CLOTHING_TYPES = ['Áo thun', 'Áo sơ mi', 'Áo khoác', 'Váy/đầm']

export const AUDIT_TYPES = [
  'Đăng nhập',
  'Tài khoản',
  'Camera',
  'Xử lý AI',
  'Mô hình AI',
  'Case',
  'Lỗi hệ thống',
]
