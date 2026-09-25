import { COLORS } from '@/constants/status'
import { DETECTIONS } from '@/mocks/detections'
import { hashUnit } from './format'

const COLOR_WORDS = {
  đỏ: 'red',
  'xanh dương': 'blue',
  'xanh lam': 'blue',
  'xanh lá': 'green',
  trắng: 'white',
  đen: 'black',
  vàng: 'yellow',
  xám: 'gray',
  be: 'beige',
  xanh: 'blue',
}

const COLOR_PATTERN = '(xanh dương|xanh lam|xanh lá|đỏ|trắng|đen|vàng|xám|be|xanh)'

export const parseDescription = (text) => {
  const t = text.toLowerCase()
  const find = (word) => {
    const m = t.match(new RegExp(`${word}\\s+(?:màu\\s+)?${COLOR_PATTERN}`))
    return m ? COLOR_WORDS[m[1]] : null
  }
  let bag = null
  if (/không\s+(mang|đeo)\s+(ba lô|balo)/.test(t)) bag = false
  else if (/(ba lô|balo)/.test(t)) bag = true
  return { shirt: find('áo(?:\\s+(?:thun|sơ mi|khoác))?'), pants: find('quần'), bag }
}

export const attributesToPrompt = (a) => {
  const parts = []
  if (a.shirt || a.type) {
    const garment = (a.type || 'áo').toLowerCase()
    parts.push(`mặc ${garment}${a.shirt ? ` màu ${COLORS[a.shirt].label.toLowerCase()}` : ''}`)
  }
  if (a.pants) parts.push(`quần màu ${COLORS[a.pants].label.toLowerCase()}`)
  if (a.bag === true) parts.push('mang ba lô')
  if (a.bag === false) parts.push('không mang ba lô')
  return parts.length ? `Một người ${parts.join(', ')}.` : 'Chưa chọn thuộc tính nào.'
}

export const validateSearch = (s) => {
  const k = Number(s.topk)
  if (s.method === 'image' && !s.imageUrl && !s.sample) {
    return 'Vui lòng tải lên ảnh đã crop chứa người cần tìm.'
  }
  if (s.method === 'text' && s.text.trim().length < 4) {
    return 'Mô tả quá ngắn. Hãy mô tả trang phục, màu sắc hoặc vật mang theo.'
  }
  if (s.method === 'attr' && !Object.values(s.attrs).some((v) => v != null)) {
    return 'Chọn ít nhất một thuộc tính ngoại hình.'
  }
  if (!Number.isInteger(k) || k < 1 || k > 100) return 'top_k phải là số nguyên dương, tối đa 100.'
  if (s.from && s.to && s.from > s.to) return 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'
  return null
}

export const runMockSearch = (s, cameraIds) => {
  const fromDay = s.from ? Number(s.from.slice(8, 10)) : 0
  const toDay = s.to ? Number(s.to.slice(8, 10)) : 99
  const pool = DETECTIONS.filter(
    (r) => cameraIds.includes(r.cam) && r.day >= fromDay && r.day <= toDay,
  )

  let query
  let label
  if (s.method === 'image') {
    query = { shirt: 'red', pants: 'black', bag: true }
    label = `Hình ảnh · ${s.imageName || 'ảnh truy vấn'} · Image Encoder`
  } else if (s.method === 'text') {
    query = parseDescription(s.text)
    label = `Văn bản · "${s.text.trim()}" · Text Encoder`
  } else {
    query = { ...s.attrs }
    label = `Thuộc tính → "${attributesToPrompt(s.attrs)}" · Text Encoder`
  }

  if (!pool.length) return { results: null, label }

  const seed = s.method + (s.text || '') + JSON.stringify(s.attrs)
  const results = pool
    .map((r) => {
      let v = 0.38 + hashUnit(r.id + seed) * 0.22
      if (query.shirt && r.shirt === query.shirt) v += 0.24
      if (query.pants && r.pants === query.pants) v += 0.12
      if (query.bag != null && r.bag === query.bag) v += 0.07
      if (query.type && r.type === query.type) v += 0.05
      return { rid: r.id, score: Math.min(0.96, v) }
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, Number(s.topk))

  return { results, label }
}
