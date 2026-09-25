export const toArea = (area) => (area ? { id: area.id, code: area.code, name: area.name } : null)

export const toSessionUser = (user) => ({
  id: user.id,
  username: user.username,
  name: user.display_name,
  role: user.role.toLowerCase(),
  status: 'active',
  area: toArea(user.area),
})
