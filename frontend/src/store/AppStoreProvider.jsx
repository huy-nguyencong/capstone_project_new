import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '@/services/api/auth'
import { onUnauthorized } from '@/services/apiService'
import { AppStoreContext } from './contexts'

const SYSTEM_ERROR =
  'Không thể đăng nhập tại thời điểm hiện tại do lỗi hệ thống. Vui lòng thử lại sau.'
const EXPIRED_NOTICE = 'Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.'

export function AppStoreProvider({ children }) {
  const [me, setMe] = useState(null)
  const [authStatus, setAuthStatus] = useState('loading')
  const [logoutNotice, setLogoutNotice] = useState(null)

  useEffect(() => {
    let active = true
    authApi
      .me()
      .then((user) => active && setMe(user))
      .catch(() => active && setMe(null))
      .finally(() => active && setAuthStatus('ready'))
    return () => {
      active = false
    }
  }, [])

  useEffect(
    () =>
      onUnauthorized((error) => {
        setMe(null)
        setLogoutNotice(error.code === 'session_expired' ? EXPIRED_NOTICE : null)
      }),
    [],
  )

  const login = useCallback(async (username, password) => {
    try {
      const user = await authApi.login(username.trim(), password)
      setMe(user)
      setLogoutNotice(null)
      return { user }
    } catch (error) {
      if (error.status && error.status < 500) return { error: error.message }
      return { error: SYSTEM_ERROR }
    }
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout().catch(() => null)
    setMe(null)
    setLogoutNotice('Bạn đã đăng xuất. Phiên làm việc đã kết thúc.')
  }, [])

  const value = useMemo(
    () => ({ me, authStatus, logoutNotice, login, logout }),
    [me, authStatus, logoutNotice, login, logout],
  )

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}
