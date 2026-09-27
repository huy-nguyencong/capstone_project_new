export const validateSearch = (s) => {
  const k = Number(s.topk)
  if (s.method === 'image' && !s.imageFile) {
    return 'Vui lòng tải lên ảnh đã crop chứa người cần tìm.'
  }
  if (s.method === 'text' && s.text.trim().length < 4) {
    return 'Mô tả quá ngắn. Hãy mô tả trang phục, màu sắc hoặc vật mang theo.'
  }
  // Mirrors the backend rule: RaSa only understands English captions.
  if (s.method === 'text' && [...s.text].some((c) => c.codePointAt(0) > 127 && /\p{L}/u.test(c))) {
    return 'Chỉ hỗ trợ mô tả bằng tiếng Anh, ví dụ "a person wearing a red shirt and black pants".'
  }
  if (s.method === 'attr' && !Object.values(s.attrs).some((v) => v != null)) {
    return 'Chọn ít nhất một thuộc tính ngoại hình.'
  }
  if (![4, 8, 12, 16].includes(k)) return 'Chọn số kết quả hiển thị: 4, 8, 12 hoặc 16.'
  if (s.from && s.to && s.from > s.to) return 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.'
  return null
}
