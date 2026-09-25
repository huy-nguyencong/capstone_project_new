import { Navigate, Outlet } from 'react-router'
import { HOME_BY_ROLE, PATHS } from '@/constants/navigation'
import { useAppStore } from '@/store/hooks'

export function RequireAuth() {
  const { me } = useAppStore()
  if (!me) return <Navigate to={PATHS.login} replace />
  return <Outlet />
}

export function RequireRole({ roles }) {
  const { me } = useAppStore()
  if (!roles.includes(me.role)) return <Navigate to={HOME_BY_ROLE[me.role]} replace />
  return <Outlet />
}

export function RedirectHome() {
  const { me } = useAppStore()
  return <Navigate to={me ? HOME_BY_ROLE[me.role] : PATHS.login} replace />
}
