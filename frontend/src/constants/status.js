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
  stopped: { label: 'Sẵn sàng, chờ dữ liệu', tone: 'ok' },
  error: { label: 'Lỗi tiến trình', tone: 'err' },
  off: { label: 'Đã tắt', tone: 'mute' },
  unknown: { label: 'Không xác định', tone: 'mute' },
}

export const USER_STATUS = {
  active: { label: 'Hoạt động', tone: 'ok' },
  locked: { label: 'Đã khóa', tone: 'err' },
  inactive: { label: 'Ngừng hoạt động', tone: 'mute' },
}

export const CASE_STATUS = {
  open: { label: 'Đang xử lý', tone: 'warn' },
  closed: { label: 'Hoàn thành', tone: 'ok' },
}

export const ROLE_LABEL = {
  admin: 'Quản trị viên',
  operator: 'Giám sát viên',
  viewer: 'Quản lý',
}

export const ROLE_TAG = {
  admin: 'outline',
  operator: 'accent',
  viewer: 'neutral',
}

export const AUDIT_EVENTS = {
  'auth.login': 'Đăng nhập',
  'auth.logout': 'Đăng xuất',
  'auth.session_expired': 'Phiên làm việc hết hạn',
  'user.created': 'Tạo tài khoản',
  'user.updated': 'Cập nhật tài khoản',
  'user.status_changed': 'Đổi trạng thái tài khoản',
  'user.role_changed': 'Đổi vai trò',
  'operator.area_assigned': 'Gán khu vực cho giám sát viên',
  'camera.created': 'Thêm camera',
  'camera.updated': 'Cập nhật camera',
  'camera.deactivated': 'Ngừng vận hành camera',
  'camera.reactivated': 'Đưa camera vận hành trở lại',
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
  'case.created': 'Tạo vụ việc',
  'case.updated': 'Cập nhật vụ việc',
  'case.closed': 'Đánh dấu vụ việc hoàn thành',
  'case.reopened': 'Mở lại vụ việc',
  'case.result_added': 'Thêm kết quả vào vụ việc',
  'case.result_removed': 'Loại kết quả khỏi vụ việc',
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
  { label: 'Vụ việc', events: eventsWithPrefix('case.') },
  {
    label: 'Lỗi hệ thống',
    events: eventsWithPrefix('system.', 'storage.', 'ai.pipeline_failed', 'ai.diagnostic_failed'),
  },
]

export const auditGroupOf = (eventType) =>
  AUDIT_GROUPS.find((group) => group.events.includes(eventType))?.label ?? 'Khác'
