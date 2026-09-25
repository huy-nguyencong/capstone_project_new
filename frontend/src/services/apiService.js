import axios from 'axios'

const CSRF_HEADER = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['get', 'head', 'options'])

let csrfToken = null

export const csrfStorage = {
  get: () => csrfToken,
  set: (token) => {
    csrfToken = token || null
  },
  clear: () => {
    csrfToken = null
  },
}

export class ApiError extends Error {
  constructor({ message, status, data, code, details, requestId }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

const toApiError = (error) => {
  if (axios.isCancel(error)) {
    return new ApiError({ message: 'Request cancelled', code: 'ERR_CANCELED' })
  }
  const { response, code, message } = error
  if (!response) {
    return new ApiError({
      message: 'Không kết nối được tới máy chủ. Vui lòng thử lại sau.',
      code: code || 'network_error',
    })
  }
  const data = response.data
  const envelope = data?.error
  return new ApiError({
    message: envelope?.message || data?.message || message,
    status: response.status,
    data,
    code: envelope?.code || code,
    details: envelope?.details,
    requestId: envelope?.request_id || response.headers?.['x-request-id'],
  })
}

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 15000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

httpClient.interceptors.request.use((config) => {
  const method = (config.method || 'get').toLowerCase()
  if (!SAFE_METHODS.has(method) && csrfToken) {
    config.headers[CSRF_HEADER] = csrfToken
  }
  return config
})

const unauthorizedHandlers = new Set()

export const onUnauthorized = (handler) => {
  unauthorizedHandlers.add(handler)
  return () => unauthorizedHandlers.delete(handler)
}

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const apiError = toApiError(error)
    if (apiError.status === 401 && !error.config?.skipUnauthorizedHandler) {
      csrfStorage.clear()
      unauthorizedHandlers.forEach((handler) => handler(apiError))
    }
    return Promise.reject(apiError)
  },
)

const request = async (config) => {
  const response = await httpClient.request(config)
  return response.data
}

export const apiService = {
  get: (url, params, config = {}) => request({ ...config, method: 'GET', url, params }),
  post: (url, data, config = {}) => request({ ...config, method: 'POST', url, data }),
  put: (url, data, config = {}) => request({ ...config, method: 'PUT', url, data }),
  patch: (url, data, config = {}) => request({ ...config, method: 'PATCH', url, data }),
  delete: (url, config = {}) => request({ ...config, method: 'DELETE', url }),
  upload: (url, formData, { onProgress, ...config } = {}) =>
    request({
      ...config,
      method: 'POST',
      url,
      data: formData,
      headers: { ...config.headers, 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    }),
}

export { httpClient }
export default apiService
