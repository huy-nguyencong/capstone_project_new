import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '@/services/api/auth'
import { onUnauthorized } from '@/services/apiService'
import { AppStoreContext } from './contexts'

const SYSTEM_ERROR =
  'Không thể đăng nhập tại thời điểm hiện tại do lỗi hệ thống. Vui lòng thử lại sau.'
const EXPIRED_NOTICE = 'Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.'

export function AppStoreProvider({ children }) {
  const [me, setMe] = useState(null)
  const [refreshAfterMs, setRefreshAfterMs] = useState(null)
  const [authStatus, setAuthStatus] = useState('loading')
  const [logoutNotice, setLogoutNotice] = useState(null)

  useEffect(() => {
    let active = true
    authApi
      .me()
      .then((session) => {
        if (!active) return
        setMe(session.user)
        setRefreshAfterMs(session.refreshAfterMs)
      })
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
        setRefreshAfterMs(null)
        setLogoutNotice(error.code === 'session_expired' ? EXPIRED_NOTICE : null)
      }),
    [],
  )

  const userId = me?.id
  useEffect(() => {
    if (!userId || !refreshAfterMs) return undefined
    let active = true
    let timer

    const schedule = (delay) => {
      timer = window.setTimeout(async () => {
        try {
          const session = await authApi.refresh()
          if (!active) return
          setMe(session.user)
          schedule(session.refreshAfterMs || delay)
        } catch (error) {
          if (!active) return
          if (!error.status || error.status >= 500) schedule(Math.min(delay, 60_000))
        }
      }, delay)
    }

    schedule(refreshAfterMs)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [userId, refreshAfterMs])

  const login = useCallback(async (username, password) => {
    try {
      const session = await authApi.login(username.trim(), password)
      setMe(session.user)
      setRefreshAfterMs(session.refreshAfterMs)
      setLogoutNotice(null)
      return { user: session.user }
    } catch (error) {
      if (error.status && error.status < 500) return { error: error.message }
      return { error: SYSTEM_ERROR }
    }
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout().catch(() => null)
    setMe(null)
    setRefreshAfterMs(null)
    setLogoutNotice('Bạn đã đăng xuất. Phiên làm việc đã kết thúc.')
  }, [])

  const value = useMemo(
    () => ({ me, authStatus, logoutNotice, login, logout }),
    [me, authStatus, logoutNotice, login, logout],
  )

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}
