import { Outlet, useLocation, useNavigate } from 'react-router'
import { NAVIGATION } from '@/constants/navigation'
import { Button } from '@/components/ui/Button'
import { useAppStore, useConfirm } from '@/store/hooks'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const { me, logout } = useAppStore()
  const confirm = useConfirm()
  const location = useLocation()
  const navigate = useNavigate()

  const askLogout = () =>
    confirm({
      title: 'Đăng xuất?',
      body: 'Phiên làm việc hiện tại sẽ kết thúc và bạn quay về màn hình đăng nhập.',
      label: 'Đăng xuất',
      onConfirm: logout,
    })

  return (
    <div className="grid min-h-screen grid-cols-1 grid-rows-[auto_1fr] bg-bg md:grid-cols-[232px_minmax(0,1fr)] md:grid-rows-1">
      <div className="hidden md:block">
        <Sidebar user={me} onLogout={askLogout} />
      </div>
      <div className="flex min-w-0 items-center gap-3 border-b border-divider bg-surface p-3 md:hidden">
        <select
          aria-label="Điều hướng"
          className="input min-w-0 flex-1"
          value={location.pathname}
          onChange={(e) => navigate(e.target.value)}
        >
          {(NAVIGATION[me.role] || []).map((section) => (
            <optgroup key={section.section} label={section.section}>
              {section.items.map((item) => (
                <option key={item.to} value={item.to}>
                  {item.label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <Button onClick={askLogout}>Đăng xuất</Button>
      </div>
      <main className="min-w-0 px-4 pt-[26px] pb-14 md:px-8">
        <Outlet />
      </main>
    </div>
  )
}
