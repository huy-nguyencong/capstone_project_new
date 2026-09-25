import apiService from '@/services/apiService'
import { toAuditLog, toStatusCamera } from '@/services/mappers'

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
    apiService.post('/admin/diagnostics/camera-pipeline', { camera_id: cameraId }),
  searchComponents: () => apiService.post('/admin/diagnostics/search-components'),
  auditLogs: async (params = {}) => {
    const page = await apiService.get('/admin/audit-logs', params, {
      paramsSerializer: { indexes: null },
    })
    return { items: page.items.map(toAuditLog), nextCursor: page.next_cursor }
  },
  auditActors: async () => (await apiService.get('/admin/audit-logs/actors')).items,
}
