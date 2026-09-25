import { COLORS } from '@/constants/status'
import { AREAS } from '@/mocks/areas'

export const describeResult = (detection, cameras, score, extra = {}) => {
  const cam = cameras.find((c) => c.id === detection.cam)
  return {
    id: detection.id,
    track: detection.track,
    camId: detection.cam,
    camName: cam.name,
    area: AREAS[cam.area],
    when: `${detection.time} · ${detection.date}`,
    osd: `${cam.name.toUpperCase()} · ${detection.date} ${detection.time}`,
    score,
    scoreText: score.toFixed(2),
    shirt: COLORS[detection.shirt].swatch,
    pants: COLORS[detection.pants].swatch,
    bag: detection.bag,
    hasFrame: !detection.noFrame,
    bbox: detection.bb,
    ...extra,
  }
}
