import apiService, { csrfStorage } from '@/services/apiService'
import { toSessionUser } from '@/services/mappers'

const toSession = ({ user, csrf_token: csrfToken, refresh_after_seconds: refreshAfterSeconds }) => {
  csrfStorage.set(csrfToken)
  const refreshAfterMs = Number(refreshAfterSeconds) * 1000
  return {
    user: toSessionUser(user),
    refreshAfterMs: Number.isFinite(refreshAfterMs) && refreshAfterMs > 0 ? refreshAfterMs : null,
  }
}

export const authApi = {
  login: async (username, password) =>
    toSession(
      await apiService.post(
        '/auth/login',
        { username, password },
        { skipUnauthorizedHandler: true },
      ),
    ),
  me: async () =>
    toSession(await apiService.get('/auth/me', undefined, { skipUnauthorizedHandler: true })),
  refresh: async () => toSession(await apiService.post('/auth/refresh')),
  logout: async () => {
    try {
      await apiService.post('/auth/logout', undefined, { skipUnauthorizedHandler: true })
    } finally {
      csrfStorage.clear()
    }
  },
}
