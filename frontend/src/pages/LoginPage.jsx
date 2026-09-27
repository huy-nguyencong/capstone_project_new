import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { Brand } from '@/components/layout/Brand'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Form'
import { HOME_BY_ROLE } from '@/constants/navigation'
import { SessionLoading } from '@/routes/guards'
import { useAppStore } from '@/store/hooks'

export default function LoginPage() {
  const { me, authStatus, login, logoutNotice } = useAppStore()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (authStatus === 'loading') return <SessionLoading />
  if (me && !busy) return <Navigate to={HOME_BY_ROLE[me.role]} replace />

  const submit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Vui lòng nhập tên đăng nhập và mật khẩu.')
      return
    }
    setBusy(true)
    setError(null)
    const res = await login(username, password)
    setBusy(false)
    if (res.error) setError(res.error)
    else navigate(HOME_BY_ROLE[res.user.role], { replace: true })
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(900px_600px_at_50%_18%,color-mix(in_srgb,var(--color-accent)_13%,transparent),transparent_62%),var(--color-bg)] px-6 py-14">
      <div className="flex w-full max-w-[480px] flex-col justify-center gap-7">
        <Brand size="lg" />
        <div>
          <h1 className="mb-2 text-[34px]">Đăng nhập</h1>
          <p className="m-0 text-sm text-neutral-400">
            Hệ thống tìm kiếm người trong dữ liệu camera giám sát. Dùng tài khoản do quản trị viên
            cấp.
          </p>
        </div>
        {logoutNotice && !error && <Alert tone="notice">{logoutNotice}</Alert>}
        <form onSubmit={submit} className="flex flex-col gap-3.5" noValidate>
          <TextField
            label="Tên đăng nhập"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Nhập tên đăng nhập"
            autoComplete="username"
          />
          <TextField
            label="Mật khẩu"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
          {error && <Alert>{error}</Alert>}
          <Button type="submit" variant="primary" disabled={busy} className="h-[38px] text-sm">
            {busy ? 'Đang xác thực…' : 'Đăng nhập'}
          </Button>
        </form>
      </div>
    </div>
  )
}
