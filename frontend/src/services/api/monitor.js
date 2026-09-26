import apiService from '@/services/apiService'
import { toAuditLog, toStatusCamera } from '@/services/mappers'

const DIAGNOSTIC_TIMEOUT_MS = 300000

export const monitorApi = {
  systemStatus: async () => {
    const body = await apiService.get('/admin/system-status')
    return {
      generatedAt: body.generated_at,
      summary: body.summary,
      cameras: body.cameras.map(toStatusCamera),
      storage: body.storage,
      encoder: body.encoder,
      worker: body.worker,
    }
  },
  cameraPipeline: (cameraId) =>
    apiService.post(
      '/admin/diagnostics/camera-pipeline',
      { camera_id: cameraId },
      { timeout: DIAGNOSTIC_TIMEOUT_MS },
    ),
  searchComponents: () =>
    apiService.post('/admin/diagnostics/search-components', undefined, {
      timeout: DIAGNOSTIC_TIMEOUT_MS,
    }),
  auditLogs: async (params = {}) => {
    const page = await apiService.get('/admin/audit-logs', params, {
      paramsSerializer: { indexes: null },
    })
    return { items: page.items.map(toAuditLog), nextCursor: page.next_cursor }
  },
  auditActors: async () => (await apiService.get('/admin/audit-logs/actors')).items,
}
