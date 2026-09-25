export const pad = (n) => String(n).padStart(2, '0')

export const nowTime = () => {
  const d = new Date()
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export const TODAY = '25/09/2026'

export const stamp = () => `${TODAY} ${nowTime()}`

export const stampMinute = () => stamp().slice(0, 16)

export const dmyToIso = (s) => `${s.slice(6, 10)}-${s.slice(3, 5)}-${s.slice(0, 2)}`

export const dmyToSortKey = (s) => s.slice(6, 10) + s.slice(3, 5) + s.slice(0, 2) + s.slice(11, 16)

export const byUpdatedDesc = (a, b) =>
  dmyToSortKey(b.updated).localeCompare(dmyToSortKey(a.updated))

export const initials = (name) =>
  name
    .split(' ')
    .slice(-2)
    .map((w) => w[0])
    .join('')

export const seededRandom = (seed) => {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return s / 2147483647
  }
}

export const hashUnit = (str) => {
  let h = 2166136261
  for (const ch of str) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) % 1000) / 1000
}

export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
