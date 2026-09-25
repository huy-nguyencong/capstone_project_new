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
