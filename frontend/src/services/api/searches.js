import { apiService } from '@/services/apiService'

const filters = (state) => ({
  top_k: Number(state.topk),
  camera_ids: state.cams,
  appeared_from: state.from || null,
  appeared_to: state.to || null,
})

export const searchesApi = {
  cameras: async () => (await apiService.get('/me/cameras')).items,
  run: (state) => {
    const shared = filters(state)
    if (state.method === 'image') {
      const body = new FormData()
      body.append('image', state.imageFile)
      body.append('top_k', String(shared.top_k))
      body.append('camera_ids', JSON.stringify(shared.camera_ids))
      if (shared.appeared_from) body.append('appeared_from', shared.appeared_from)
      if (shared.appeared_to) body.append('appeared_to', shared.appeared_to)
      return apiService.upload('/searches/image', body)
    }
    if (state.method === 'text') {
      return apiService.post('/searches/text', { ...shared, text: state.text.trim() })
    }
    return apiService.post('/searches/attributes', {
      ...shared,
      attributes: {
        upper_color: state.attrs.shirt,
        lower_color: state.attrs.pants,
        upper_type: state.attrs.type,
        has_backpack: state.attrs.bag,
      },
    })
  },
}
