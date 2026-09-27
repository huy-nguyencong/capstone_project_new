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
  noRtsp: { label: 'Video tải lên', tone: 'mute' },
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
  red: { label: 'Red', swatch: 'oklch(0.58 0.16 25)' },
  blue: { label: 'Blue', swatch: 'oklch(0.55 0.12 250)' },
  white: { label: 'White', swatch: 'oklch(0.9 0.01 260)' },
  black: { label: 'Black', swatch: 'oklch(0.3 0.01 260)' },
  green: { label: 'Green', swatch: 'oklch(0.58 0.1 150)' },
  yellow: { label: 'Yellow', swatch: 'oklch(0.82 0.13 90)' },
  gray: { label: 'Gray', swatch: 'oklch(0.62 0.01 260)' },
  beige: { label: 'Beige', swatch: 'oklch(0.78 0.04 70)' },
}

export const PANTS_COLORS = ['black', 'blue', 'gray', 'beige']

// Values match the backend attribute enum; labels are the English words used in the prompt.
export const CLOTHING_TYPES = [
  { value: 't_shirt', label: 'T-shirt' },
  { value: 'shirt', label: 'Shirt' },
  { value: 'jacket', label: 'Jacket' },
  { value: 'dress', label: 'Dress' },
]

export const AUDIT_EVENTS = {
  'auth.login': 'Đăng nhập',
  'auth.logout': 'Đăng xuất',
  'auth.session_expired': 'Phiên làm việc hết hạn',
  'user.created': 'Tạo tài khoản',
  'user.updated': 'Cập nhật tài khoản',
  'user.status_changed': 'Đổi trạng thái tài khoản',
  'user.role_changed': 'Đổi vai trò',
  'operator.area_assigned': 'Gán khu vực cho Operator',
  'camera.created': 'Thêm camera',
  'camera.updated': 'Cập nhật camera',
  'camera.deactivated': 'Ngừng vận hành camera',
  'camera.connection_tested': 'Kiểm tra kết nối RTSP',
  'ai.state_changed': 'Bật/tắt xử lý AI',
  'job.created': 'Tạo job xử lý video',
  'job.cancel_requested': 'Yêu cầu hủy job',
  'job.finished': 'Job xử lý kết thúc',
  'ai.config_requested': 'Yêu cầu đổi mô hình',
  'ai.config_applied': 'Áp dụng mô hình',
  'ai.config_failed': 'Áp dụng mô hình thất bại',
  'ai.pipeline_failed': 'Pipeline AI lỗi',
  'ai.diagnostic_failed': 'Kiểm tra AI phát hiện lỗi',
  'case.created': 'Tạo Case',
  'case.updated': 'Cập nhật Case',
  'case.result_added': 'Thêm kết quả vào Case',
  'case.result_removed': 'Loại kết quả khỏi Case',
  'storage.track_failed': 'Lưu track thất bại',
  'storage.track_requeued': 'Xếp lại track',
  'storage.orphans_deleted': 'Dọn dữ liệu mồ côi',
  'system.technical_failure': 'Lỗi kỹ thuật',
}

const eventsWithPrefix = (...prefixes) =>
  Object.keys(AUDIT_EVENTS).filter((event) => prefixes.some((p) => event.startsWith(p)))

export const AUDIT_GROUPS = [
  { label: 'Đăng nhập', events: eventsWithPrefix('auth.') },
  { label: 'Tài khoản', events: eventsWithPrefix('user.', 'operator.') },
  { label: 'Camera', events: eventsWithPrefix('camera.') },
  { label: 'Xử lý AI', events: eventsWithPrefix('ai.state_changed', 'job.') },
  { label: 'Mô hình AI', events: eventsWithPrefix('ai.config_') },
  { label: 'Case', events: eventsWithPrefix('case.') },
  { label: 'Lỗi hệ thống', events: eventsWithPrefix('system.', 'storage.') },
]

export const auditGroupOf = (eventType) =>
  AUDIT_GROUPS.find((group) => group.events.includes(eventType))?.label ?? 'Khác'
