import { useCallback, useEffect, useMemo, useState } from 'react'
import { AUDIT_LOGS } from '@/mocks/auditLogs'
import { CAMERAS } from '@/mocks/cameras'
import { CASES } from '@/mocks/cases'
import { USERS } from '@/mocks/users'
import { authApi } from '@/services/api/auth'
import { onUnauthorized } from '@/services/apiService'
import { stamp, stampMinute } from '@/utils/format'
import { AppStoreContext } from './contexts'

const SYSTEM_ERROR =
  'Không thể đăng nhập tại thời điểm hiện tại do lỗi hệ thống. Vui lòng thử lại sau.'
const EXPIRED_NOTICE = 'Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.'

export function AppStoreProvider({ children }) {
  const [users, setUsers] = useState(USERS)
  const [cameras, setCameras] = useState(CAMERAS)
  const [cases, setCases] = useState(CASES)
  const [logs, setLogs] = useState(AUDIT_LOGS)
  const [models, setModels] = useState({ det: 'yolov8m', trk: 'bytetrack' })
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

  const log = useCallback(
    (type, action, target, ok = true, detail) => {
      const user = me?.username ?? 'system'
      setLogs((prev) => [{ t: stamp(), user, type, action, target, ok, detail }, ...prev])
    },
    [me],
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

  const addUser = useCallback((user) => {
    setUsers((prev) => [...prev, { id: `u${Date.now()}`, status: 'active', last: '—', ...user }])
  }, [])

  const updateUser = useCallback((id, patch) => {
    setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, ...patch } : u)))
  }, [])

  const addCamera = useCallback((camera) => {
    setCameras((prev) => [...prev, { id: `c${Date.now()}`, ...camera }])
  }, [])

  const updateCamera = useCallback((id, patch) => {
    setCameras((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  }, [])

  const createCase = useCallback(
    ({ title, note, rid, score }) => {
      const next = Math.max(...cases.map((c) => Number(c.id.slice(3)))) + 1
      const id = `CS-${String(next).padStart(4, '0')}`
      const ts = stampMinute()
      setCases((prev) => [
        {
          id,
          title,
          note,
          owner: me?.id,
          created: ts,
          updated: ts,
          items: [{ rid, score, saved: ts }],
        },
        ...prev,
      ])
      return id
    },
    [cases, me],
  )

  const addToCase = useCallback((caseId, rid, score) => {
    const ts = stampMinute()
    setCases((prev) =>
      prev.map((c) =>
        c.id === caseId ? { ...c, updated: ts, items: [...c.items, { rid, score, saved: ts }] } : c,
      ),
    )
  }, [])

  const removeFromCase = useCallback((caseId, rid) => {
    const ts = stampMinute()
    setCases((prev) =>
      prev.map((c) =>
        c.id === caseId ? { ...c, updated: ts, items: c.items.filter((i) => i.rid !== rid) } : c,
      ),
    )
  }, [])

  const updateCase = useCallback((caseId, patch) => {
    const ts = stampMinute()
    setCases((prev) => prev.map((c) => (c.id === caseId ? { ...c, ...patch, updated: ts } : c)))
  }, [])

  const value = useMemo(
    () => ({
      me,
      authStatus,
      users,
      cameras,
      cases,
      logs,
      models,
      logoutNotice,
      login,
      logout,
      log,
      addUser,
      updateUser,
      addCamera,
      updateCamera,
      setModels,
      createCase,
      addToCase,
      removeFromCase,
      updateCase,
    }),
    [
      me,
      authStatus,
      users,
      cameras,
      cases,
      logs,
      models,
      logoutNotice,
      login,
      logout,
      log,
      addUser,
      updateUser,
      addCamera,
      updateCamera,
      createCase,
      addToCase,
      removeFromCase,
      updateCase,
    ],
  )

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>
}
