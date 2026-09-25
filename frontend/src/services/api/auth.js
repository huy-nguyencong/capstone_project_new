import apiService, { csrfStorage } from '@/services/apiService'
import { toSessionUser } from '@/services/mappers'

const toSession = ({ user, csrf_token: csrfToken }) => {
  csrfStorage.set(csrfToken)
  return toSessionUser(user)
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
  logout: async () => {
    try {
      await apiService.post('/auth/logout', undefined, { skipUnauthorizedHandler: true })
    } finally {
      csrfStorage.clear()
    }
  },
}
