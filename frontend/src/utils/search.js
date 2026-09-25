import { COLORS } from '@/constants/status'

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
  if (s.method === 'image' && !s.imageFile) {
    return 'Vui lòng tải lên ảnh đã crop chứa người cần tìm.'
  }
  if (s.method === 'text' && s.text.trim().length < 4) {
    return 'Mô tả quá ngắn. Hãy mô tả trang phục, màu sắc hoặc vật mang theo.'
  }
  if (s.method === 'attr' && !Object.values(s.attrs).some((v) => v != null)) {
    return 'Chọn ít nhất một thuộc tính ngoại hình.'
  }
  if (![4, 8, 12, 16].includes(k)) return 'top_k phải là 4, 8, 12 hoặc 16.'
  if (s.from && s.to && s.from > s.to) return 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'
  return null
}
