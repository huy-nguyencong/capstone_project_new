import axios from 'axios'

const TOKEN_KEY = 'access_token'

export const tokenStorage = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  constructor({ message, status, data, code }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
    this.code = code
  }
}

const toApiError = (error) => {
  if (axios.isCancel(error)) {
    return new ApiError({ message: 'Request cancelled', code: 'ERR_CANCELED' })
  }
  const { response, code, message } = error
  if (!response) {
    return new ApiError({ message: message || 'Network error', code })
  }
  const data = response.data
  return new ApiError({
    message: data?.message || data?.detail || message,
    status: response.status,
    data,
    code,
  })
}

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

httpClient.interceptors.request.use((config) => {
  const token = tokenStorage.get()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
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
    if (apiError.status === 401) {
      tokenStorage.clear()
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
