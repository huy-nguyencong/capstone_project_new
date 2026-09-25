import { Outlet } from 'react-router'
import { useAppStore, useConfirm } from '@/store/hooks'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const { me, logout } = useAppStore()
  const confirm = useConfirm()

  const askLogout = () =>
    confirm({
      title: 'Đăng xuất?',
      body: 'Phiên làm việc hiện tại sẽ kết thúc và bạn quay về màn hình đăng nhập.',
      label: 'Đăng xuất',
      onConfirm: logout,
    })

  return (
    <div className="grid min-h-screen grid-cols-[232px_minmax(0,1fr)] bg-bg">
      <Sidebar user={me} onLogout={askLogout} />
      <main className="min-w-0 px-8 pt-[26px] pb-14">
        <Outlet />
      </main>
    </div>
  )
}
