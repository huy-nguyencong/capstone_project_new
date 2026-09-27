import { useCallback, useEffect, useMemo, useState } from 'react'
import { authApi } from '@/services/api/auth'
import { onUnauthorized } from '@/services/apiService'
import { AppStoreContext } from './contexts'

const SYSTEM_ERROR =
  'Không thể đăng nhập tại thời điểm hiện tại do lỗi hệ thống. Vui lòng thử lại sau.'
const EXPIRED_NOTICE = 'Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.'
const ACTIVITY_KEY = 'person-search.last-activity'
const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart']

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

  // UC-15: only real user activity extends the session. Background polling must not keep an
  // idle session alive, so refresh is skipped while idle and the session ends after the idle
  // timeout (the server refreshes every idle/2). Activity is shared across tabs.
  const userId = me?.id
  useEffect(() => {
    if (!userId || !refreshAfterMs) return undefined
    const idleMs = refreshAfterMs * 2
    const checkMs = Math.min(refreshAfterMs, 30_000)
    let active = true
    let timer
    let lastActivity = Date.now()
    let lastRefresh = Date.now()
    let lastShared = 0

    const readShared = () => {
      try {
        return Number(localStorage.getItem(ACTIVITY_KEY)) || 0
      } catch {
        return 0
      }
    }
    const markActive = () => {
      lastActivity = Date.now()
      if (lastActivity - lastShared < 5_000) return
      lastShared = lastActivity
      try {
        localStorage.setItem(ACTIVITY_KEY, String(lastActivity))
      } catch {
        // Per-tab tracking still works without storage.
      }
    }
    markActive()
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, markActive, { passive: true }))

    const tick = async () => {
      if (!active) return
      const now = Date.now()
      const latest = Math.max(lastActivity, readShared())
      if (now - latest >= idleMs) {
        await authApi.logout().catch(() => null)
        if (!active) return
        setMe(null)
        setRefreshAfterMs(null)
        setLogoutNotice(EXPIRED_NOTICE)
        return
      }
      if (latest > lastRefresh && now - lastRefresh >= refreshAfterMs) {
        try {
          const session = await authApi.refresh()
          if (!active) return
          lastRefresh = Date.now()
          setMe(session.user)
        } catch {
          // 401 is handled by the API interceptor; transient errors retry on the next tick.
        }
      }
      if (active) timer = window.setTimeout(tick, checkMs)
    }

    timer = window.setTimeout(tick, checkMs)
    return () => {
      active = false
      window.clearTimeout(timer)
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, markActive))
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
