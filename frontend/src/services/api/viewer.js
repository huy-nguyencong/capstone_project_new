import apiService from '@/services/apiService'
import { toCaseSummary } from '@/services/mappers'

export const viewerApi = {
  dashboard: async (recentLimit = 6) => {
    const body = await apiService.get('/viewer/dashboard', { recent_limit: recentLimit })
    return {
      totalCases: body.total_cases,
      totalCaseResults: body.total_case_results,
      openCases: body.open_cases,
      closedCases: body.closed_cases,
      recentCases: body.recent_cases.map(toCaseSummary),
    }
  },
  operators: async () =>
    (await apiService.get('/viewer/operators')).items.map((item) => ({
      id: item.id,
      name: item.display_name,
      status: item.status.toLowerCase(),
    })),
}
