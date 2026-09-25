import { CLOTHING_TYPES, COLORS, PANTS_COLORS } from '@/constants/status'
import { pad, seededRandom } from '@/utils/format'

const build = () => {
  const r = seededRandom(11)
  const pick = (a) => a[Math.floor(r() * a.length)]
  const cams = ['c1', 'c2', 'c3', 'c6', 'c9', 'c10', 'c1', 'c2', 'c5']
  const shirts = Object.keys(COLORS)
  const out = []
  for (let i = 0; i < 64; i++) {
    const w = 7 + r() * 4
    const h = w * 4.2
    const day = [25, 25, 24, 23][i % 4]
    const hh = 7 + Math.floor(r() * 13)
    const mm = Math.floor(r() * 60)
    const ss = Math.floor(r() * 60)
    out.push({
      id: `r${i + 1}`,
      track: `T-${40210 + i * 13}`,
      cam: pick(cams),
      day,
      ts: day * 86400 + hh * 3600 + mm * 60 + ss,
      date: `${pad(day)}/09/2026`,
      time: `${pad(hh)}:${pad(mm)}:${pad(ss)}`,
      shirt: pick(shirts),
      pants: pick(PANTS_COLORS),
      bag: r() < 0.4,
      type: pick(CLOTHING_TYPES.slice(0, 3)),
      bb: {
        x: +(6 + r() * (86 - w)).toFixed(1),
        y: +(8 + r() * (88 - h)).toFixed(1),
        w: +w.toFixed(1),
        h: +h.toFixed(1),
      },
    })
  }
  Object.assign(out[0], { cam: 'c1', shirt: 'red', pants: 'black', bag: true })
  Object.assign(out[5], { cam: 'c2', shirt: 'red', pants: 'black', bag: true })
  Object.assign(out[9], { cam: 'c3', shirt: 'red', pants: 'blue', bag: true })
  Object.assign(out[14], { cam: 'c1', shirt: 'red', pants: 'black', bag: false })
  Object.assign(out[18], { cam: 'c2' })
  Object.assign(out[33], { cam: 'c2', noFrame: true })
  ;[20, 21].forEach((i) => (out[i].cam = 'c6'))
  ;[25, 30].forEach((i) => (out[i].cam = 'c9'))
  out[26].cam = 'c10'
  return out
}

export const DETECTIONS = build()

export const findDetection = (id) => DETECTIONS.find((d) => d.id === id)
