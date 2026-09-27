const timeFormatter = new Intl.DateTimeFormat('vi-VN', {
  dateStyle: 'short',
  timeStyle: 'medium',
})

const clockFormatter = new Intl.DateTimeFormat('vi-VN', { timeStyle: 'medium' })
const dayFormatter = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const percentBox = (box) =>
  box
    ? {
        x: (box.x / box.frame_width) * 100,
        y: (box.y / box.frame_height) * 100,
        w: (box.width / box.frame_width) * 100,
        h: (box.height / box.frame_height) * 100,
      }
    : null

export const describeSearchResult = (item) => {
  const appearedAt = new Date(item.appeared_at)
  return {
    id: item.track_id,
    track: item.track_id,
    camId: item.camera.id,
    camName: item.camera.name,
    area: item.area.name,
    appearedAt: item.appeared_at,
    when: timeFormatter.format(appearedAt),
    time: clockFormatter.format(appearedAt),
    day: dayFormatter.format(appearedAt),
    osd: `${item.camera.name.toUpperCase()} · ${timeFormatter.format(appearedAt)}`,
    score: item.matching_score,
    scoreText: item.matching_score.toFixed(3),
    scoreShort: item.matching_score.toFixed(2),
    hasFrame: true,
    cropUrl: item.crop_url,
    frameUrl: item.frame_url,
    bbox: percentBox(item.bbox),
  }
}

export const describeCaseResult = (item) => {
  const appearedAt = new Date(item.appeared_at)
  return {
    id: item.id,
    track: item.track_id,
    camName: item.camera_name,
    area: item.area_name,
    appearedAt: item.appeared_at,
    when: timeFormatter.format(appearedAt),
    osd: `${item.camera_name.toUpperCase()} · ${timeFormatter.format(appearedAt)}`,
    score: null,
    scoreText: null,
    saved: timeFormatter.format(new Date(item.saved_at)),
    hasFrame: true,
    cropUrl: item.crop_url,
    frameUrl: item.frame_url,
    bbox: percentBox(item.bbox),
  }
}
