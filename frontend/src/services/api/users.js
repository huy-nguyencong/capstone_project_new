import apiService from '@/services/apiService'
import { toArea, toUser } from '@/services/mappers'

export const usersApi = {
  areas: async () => (await apiService.get('/areas')).items.map(toArea),
  list: async (params = {}) => {
    const page = await apiService.get('/admin/users', params)
    return { items: page.items.map(toUser), nextCursor: page.next_cursor }
  },
  get: async (id) => toUser(await apiService.get(`/admin/users/${id}`)),
  create: async (data) => toUser(await apiService.post('/admin/users', data)),
  update: async (id, data) => toUser(await apiService.patch(`/admin/users/${id}`, data)),
  lock: async (id) => toUser(await apiService.post(`/admin/users/${id}/lock`)),
  unlock: async (id) => toUser(await apiService.post(`/admin/users/${id}/unlock`)),
  deactivate: async (id) => toUser(await apiService.post(`/admin/users/${id}/deactivate`)),
}
