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
  // Mark a case completed right after saving into it. Reads the current version first so a
  // concurrent edit does not reject the request. Returns null on success or an error message.
  markCompleted: async (id) => {
    try {
      const fresh = await apiService.get(`/cases/${id}`)
      await apiService.patch(`/cases/${id}`, { status: 'CLOSED', version: fresh.case.version })
      return null
    } catch (error) {
      return error.message
    }
  },
}
