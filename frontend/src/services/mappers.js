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
