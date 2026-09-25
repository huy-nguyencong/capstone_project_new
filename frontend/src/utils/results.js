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

const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'short',
  timeStyle: 'medium',
})

export const describeSearchResult = (item) => {
  const box = item.bbox
  const appearedAt = new Date(item.appeared_at)
  return {
    id: item.track_id,
    track: item.track_id,
    camId: item.camera.id,
    camName: item.camera.name,
    area: item.area.name,
    appearedAt: item.appeared_at,
    when: timeFormatter.format(appearedAt),
    osd: `${item.camera.name.toUpperCase()} · ${timeFormatter.format(appearedAt)}`,
    score: item.matching_score,
    scoreText: item.matching_score.toFixed(3),
    hasFrame: true,
    cropUrl: item.crop_url,
    frameUrl: item.frame_url,
    bbox: {
      x: (box.x / box.frame_width) * 100,
      y: (box.y / box.frame_height) * 100,
      w: (box.width / box.frame_width) * 100,
      h: (box.height / box.frame_height) * 100,
    },
  }
}
