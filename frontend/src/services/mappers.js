export const toArea = (area) => (area ? { id: area.id, code: area.code, name: area.name } : null)

export const toSessionUser = (user) => ({
  id: user.id,
  username: user.username,
  name: user.display_name,
  role: user.role.toLowerCase(),
  status: 'active',
  area: toArea(user.area),
})

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export const toUser = (user) => ({
  id: user.id,
  username: user.username,
  name: user.display_name,
  role: user.role.toLowerCase(),
  status: user.status.toLowerCase(),
  area: toArea(user.area),
  last: user.last_login_at ? dateTimeFormatter.format(new Date(user.last_login_at)) : '—',
  createdAt: user.created_at,
  version: user.version,
})

export const toCamera = (camera) => ({
  id: camera.id,
  code: camera.code,
  name: camera.name,
  area: toArea(camera.area),
  lifecycle: camera.status,
  status:
    camera.status === 'RETIRED'
      ? 'retired'
      : camera.status !== 'ACTIVE'
        ? 'unknown'
        : camera.rtsp_status === 'ONLINE'
          ? 'online'
          : ['OFFLINE', 'ERROR'].includes(camera.rtsp_status)
            ? 'offline'
            : 'unverified',
  rtsp: camera.rtsp_url_masked || '',
  hasRtsp: camera.has_rtsp,
  ai: camera.ai_enabled,
  aiState: !camera.ai_enabled
    ? 'off'
    : { RUNNING: 'running', QUEUED: 'starting', IDLE: 'stopped', ERROR: 'error' }[
        camera.worker_state
      ] || 'unknown',
  lastCheckedAt: camera.last_checked_at,
  version: camera.version,
})

export const shortId = (id) => (id ? id.slice(0, 8) : '')

export const toCaseSummary = (item) => ({
  id: item.id,
  code: shortId(item.id),
  title: item.title,
  note: item.note || '',
  owner: {
    id: item.owner.id,
    name: item.owner.display_name,
    status: item.owner.status.toLowerCase(),
  },
  resultCount: item.result_count,
  status: (item.status || 'OPEN').toLowerCase(),
  closed: item.closed_at ? dateTimeFormatter.format(new Date(item.closed_at)) : null,
  created: dateTimeFormatter.format(new Date(item.created_at)),
  updated: dateTimeFormatter.format(new Date(item.updated_at)),
  version: item.version,
})

const WORKER_AI_STATE = {
  DISABLED: 'off',
  RUNNING: 'running',
  QUEUED: 'starting',
  IDLE: 'stopped',
  ERROR: 'error',
}

const CONNECTION_STATUS = {
  ONLINE: 'online',
  OFFLINE: 'offline',
  ERROR: 'offline',
  UNKNOWN: 'unverified',
  NOT_CONFIGURED: 'noRtsp',
}

const formatDateTime = (value) => (value ? dateTimeFormatter.format(new Date(value)) : '—')

export const toStatusCamera = (camera) => ({
  id: camera.id,
  code: camera.code,
  name: camera.name,
  areaName: camera.area_name,
  status: camera.status === 'ACTIVE' ? CONNECTION_STATUS[camera.connection] : 'unknown',
  connection: camera.connection,
  ai: camera.ai_enabled,
  aiState: WORKER_AI_STATE[camera.worker_state] || 'unknown',
  category: camera.category,
  activeJobId: camera.active_job_id,
  lastChecked: formatDateTime(camera.last_checked_at),
  lastHeartbeat: formatDateTime(camera.last_heartbeat_at),
  lastError: camera.last_error,
  metrics: camera.metrics,
})

export const toAuditLog = (item) => ({
  id: item.id,
  at: formatDateTime(item.occurred_at),
  actor: item.actor?.username ?? 'system',
  eventType: item.event_type,
  targetType: item.target_type,
  targetId: item.target_id,
  target: item.target_label || (item.target_id ? shortId(item.target_id) : '—'),
  ok: item.result === 'SUCCESS',
  metadata: item.metadata || {},
})
