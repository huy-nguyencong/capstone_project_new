const GARMENT_WORDS = { t_shirt: 't-shirt', shirt: 'shirt', jacket: 'jacket', dress: 'dress' }

// Mirrors backend services/searches.py attributes_prompt so the preview is the encoded sentence.
export const attributesToPrompt = (a) => {
  const garments = []
  if (a.shirt || a.type) {
    garments.push([a.shirt, GARMENT_WORDS[a.type] || 'top'].filter(Boolean).join(' '))
  }
  if (a.pants) garments.push(`${a.pants} pants`)
  const parts = garments.length ? [`wearing ${garments.join(' and ')}`] : []
  if (a.bag === true) parts.push('carrying a backpack')
  if (a.bag === false) parts.push('without a backpack')
  return parts.length ? `A person ${parts.join(', ')}.` : 'Chưa chọn thuộc tính nào.'
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
  if (s.method === 'attr' && s.attrs.type === 'dress' && s.attrs.pants) {
    return 'Dress không đi kèm Lower color. Bỏ chọn một trong hai.'
  }
  if (![4, 8, 12, 16].includes(k)) return 'top_k phải là 4, 8, 12 hoặc 16.'
  if (s.from && s.to && s.from > s.to) return 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'
  return null
}
