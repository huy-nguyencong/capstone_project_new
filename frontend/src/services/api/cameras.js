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
export const aiApi = {
  models: () => apiService.get('/admin/ai/models'),
  config: () => apiService.get('/admin/ai/config'),
  apply: (data) => apiService.put('/admin/ai/config', data),
}
