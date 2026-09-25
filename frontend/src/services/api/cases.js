import apiService from '@/services/apiService'
import { toCaseSummary } from '@/services/mappers'
import { describeCaseResult } from '@/utils/results'

const toDetail = (body) => ({
  case: toCaseSummary(body.case),
  results: body.results.map(describeCaseResult),
})

export const casesApi = {
  list: async (params = {}) => {
    const page = await apiService.get('/cases', params)
    return { items: page.items.map(toCaseSummary), nextCursor: page.next_cursor }
  },
  get: async (id) => toDetail(await apiService.get(`/cases/${id}`)),
  create: async (data) => toDetail(await apiService.post('/cases', data)),
  update: async (id, data) => toCaseSummary(await apiService.patch(`/cases/${id}`, data)),
  addResult: async (id, trackId) =>
    describeCaseResult(await apiService.post(`/cases/${id}/results`, { track_id: trackId })),
  removeResult: (id, resultId) => apiService.delete(`/cases/${id}/results/${resultId}`),
}
