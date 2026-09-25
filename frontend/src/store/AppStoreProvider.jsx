import { useCallback, useMemo, useState } from 'react'
import { AUDIT_LOGS } from '@/mocks/auditLogs'
import { CAMERAS } from '@/mocks/cameras'
import { CASES } from '@/mocks/cases'
import { USERS } from '@/mocks/users'
import { stamp, stampMinute, wait } from '@/utils/format'
import { AppStoreContext } from './contexts'

const SESSION_KEY = 'visiontrace.session'

const readSession = () => {
  try {
    return sessionStorage.getItem(SESSION_KEY)
  } catch {
    return null
  }
}

const writeSession = (id) => {
  try {
    if (id) sessionStorage.setItem(SESSION_KEY, id)
    else sessionStorage.removeItem(SESSION_KEY)
  } catch {
    return
  }
}

export function AppStoreProvider({ children }) {
  const [users, setUsers] = useState(USERS)
  const [cameras, setCameras] = useState(CAMERAS)
  const [cases, setCases] = useState(CASES)
  const [logs, setLogs] = useState(AUDIT_LOGS)
  const [models, setModels] = useState({ det: 'yolov8m', trk: 'bytetrack' })
  const [userId, setUserId] = useState(() => {
    const id = readSession()
    return USERS.some((u) => u.id === id && u.status === 'active') ? id : null
  })
  const [logoutNotice, setLogoutNotice] = useState(null)

  const me = users.find((u) => u.id === userId) ?? null

  const log = useCallback(
    (type, action, target, ok = true, detail) => {
      const user = me?.username ?? 'system'
      setLogs((prev) => [{ t: stamp(), user, type, action, target, ok, detail }, ...prev])
    },
    [me],
  )

  const login = useCallback(
    async (username, password) => {
      await wait(650)
      const un = username.trim().toLowerCase()
      if (un === 'error') {
        return {
          error:
            'Không thể đăng nhập tại thời điểm hiện tại do lỗi hệ thống. Vui lòng thử lại sau.',
        }
      }
      const user = users.find((u) => u.username === un)
      if (!user || password === 'sai') {
        return { error: 'Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng nhập lại.' }
      }
      if (user.status !== 'active') {
        return {
          error:
            'Tài khoản đã bị khóa hoặc ngừng hoạt động và không có quyền truy cập hệ thống. Liên hệ Admin.',
        }
      }
      setUserId(user.id)
      setLogoutNotice(null)
      writeSession(user.id)
      return { user }
    },
    [users],
  )

  const logout = useCallback(() => {
    log('Đăng nhập', 'Đăng xuất', me?.username ?? '')
    setUserId(null)
    writeSession(null)
    setLogoutNotice('Bạn đã đăng xuất. Phiên làm việc đã kết thúc.')
  }, [log, me])

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
