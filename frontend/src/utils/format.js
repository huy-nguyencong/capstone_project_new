export const pad = (n) => String(n).padStart(2, '0')

export const nowTime = () => {
  const d = new Date()
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export const initials = (name) =>
  name
    .split(' ')
    .slice(-2)
    .map((w) => w[0])
    .join('')
