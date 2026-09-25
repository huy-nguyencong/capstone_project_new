import apiService from '@/services/apiService'

export const jobsApi = {
  list: (params = {}) => apiService.get('/admin/processing-jobs', params),
  get: (id) => apiService.get(`/admin/processing-jobs/${id}`),
  cancel: (id) => apiService.post(`/admin/processing-jobs/${id}/cancel`),
  upload: (cameraId, data, key, onProgress) =>
    apiService.upload(`/admin/cameras/${cameraId}/processing-jobs`, data, {
      timeout: 0,
      headers: { 'Idempotency-Key': key },
      onProgress: (event) =>
        onProgress(event.total ? Math.round((event.loaded / event.total) * 100) : null),
    }),
}
