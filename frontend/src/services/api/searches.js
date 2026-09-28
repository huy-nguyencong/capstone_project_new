import { apiService } from '@/services/apiService'

// The first search after the API starts loads the RaSa query encoder (about 15-45 s on CPU),
// longer than the default request timeout.
const SEARCH_TIMEOUT_MS = 120000

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
    const config = { timeout: SEARCH_TIMEOUT_MS }
    if (state.method === 'image') {
      const body = new FormData()
      body.append('image', state.imageFile)
      body.append('top_k', String(shared.top_k))
      body.append('camera_ids', JSON.stringify(shared.camera_ids))
      if (shared.appeared_from) body.append('appeared_from', shared.appeared_from)
      if (shared.appeared_to) body.append('appeared_to', shared.appeared_to)
      return apiService.upload('/searches/image', body, config)
    }
    if (state.method === 'text') {
      return apiService.post('/searches/text', { ...shared, text: state.text.trim() }, config)
    }
    return apiService.post(
      '/searches/attributes',
      {
        ...shared,
        // Only chosen attributes are sent; field names match the API.
        attributes: Object.fromEntries(Object.entries(state.attrs).filter(([, v]) => v != null)),
      },
      config,
    )
  },
}
