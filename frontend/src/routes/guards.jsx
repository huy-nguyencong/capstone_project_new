import { Navigate, Outlet } from 'react-router'
import { Spinner } from '@/components/ui/Spinner'
import { HOME_BY_ROLE, PATHS } from '@/constants/navigation'
import { useAppStore } from '@/store/hooks'

export function SessionLoading() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg text-neutral-400">
      <Spinner size={22} />
    </div>
  )
}

export function RequireAuth() {
  const { me, authStatus } = useAppStore()
  if (authStatus === 'loading') return <SessionLoading />
  if (!me) return <Navigate to={PATHS.login} replace />
  return <Outlet />
}

export function RequireRole({ roles }) {
  const { me } = useAppStore()
  if (!roles.includes(me.role)) return <Navigate to={HOME_BY_ROLE[me.role]} replace />
  return <Outlet />
}

export function RedirectHome() {
  const { me, authStatus } = useAppStore()
  if (authStatus === 'loading') return <SessionLoading />
  return <Navigate to={me ? HOME_BY_ROLE[me.role] : PATHS.login} replace />
}
