import apiService from '@/services/apiService'
import { toCamera } from '@/services/mappers'

export const camerasApi = {
  list: async (params = {}) => {
    const page = await apiService.get('/admin/cameras', params)
    return { items: page.items.map(toCamera), nextCursor: page.next_cursor }
  },
  get: async (id) => toCamera(await apiService.get(`/admin/cameras/${id}`)),
  create: async (data) => toCamera(await apiService.post('/admin/cameras', data)),
  update: async (id, data) => toCamera(await apiService.patch(`/admin/cameras/${id}`, data)),
  retire: async (id) => toCamera(await apiService.post(`/admin/cameras/${id}/retire`)),
  reactivate: async (id) => toCamera(await apiService.post(`/admin/cameras/${id}/reactivate`)),
  test: (id) => apiService.post(`/admin/cameras/${id}/connection-tests`),
  state: async (id, enabled) =>
    toCamera(await apiService.put(`/admin/cameras/${id}/ai-state`, { enabled })),
}
// Applying a Detector/Tracker pair first loads the candidate models, including RaSa, on the
// server (tens of seconds on CPU), which exceeds the default request timeout.
const AI_CONFIG_APPLY_TIMEOUT_MS = 180000

export const aiApi = {
  models: () => apiService.get('/admin/ai/models'),
  config: () => apiService.get('/admin/ai/config'),
  apply: (data) =>
    apiService.put('/admin/ai/config', data, { timeout: AI_CONFIG_APPLY_TIMEOUT_MS }),
}
