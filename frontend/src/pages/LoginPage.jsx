import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { Brand } from '@/components/layout/Brand'
import { BoundingBox, SceneFrame } from '@/components/person/SceneFrame'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Form'
import { Dot } from '@/components/ui/StatusDot'
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
    <div className="grid min-h-screen grid-cols-[repeat(auto-fit,minmax(380px,1fr))] bg-[radial-gradient(900px_600px_at_12%_18%,color-mix(in_srgb,var(--color-accent)_13%,transparent),transparent_62%),var(--color-bg)]">
      <div className="flex max-w-[600px] flex-col justify-center gap-7 px-[8vw] py-14">
        <Brand size="lg" />
        <div>
          <h1 className="mb-2 text-[34px]">Đăng nhập</h1>
          <p className="text-muted m-0 text-sm text-pretty">
            Dùng tài khoản được cấp. Chức năng và dữ liệu hiển thị theo vai trò và phạm vi quyền của
            bạn.
          </p>
        </div>
        {logoutNotice && !error && <Alert tone="notice">{logoutNotice}</Alert>}
        <form onSubmit={submit} className="flex flex-col gap-3.5" noValidate>
          <TextField
            label="Tên đăng nhập"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="vd. khoa.tran"
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

      <div className="hidden items-center py-12 pr-[6vw] lg:flex">
        <SceneFrame aspect="16/10" className="w-full rounded-lg shadow-md">
          <div className="absolute top-3.5 left-4 font-mono text-[11px] font-medium tracking-[0.04em] text-neutral-300">
            A-01 CỔNG CHÍNH · 25/09/2026 14:32:08
          </div>
          <div className="absolute top-3.5 right-4 flex items-center gap-1.5 text-[11px] text-neutral-300">
            <Dot tone="ok" size={6} />
            RTSP · 25 fps
          </div>
          <BoundingBox box={{ x: 58, y: 30, w: 10, h: 46 }} label="T-40210 · 0.91" />
          <BoundingBox box={{ x: 24, y: 38, w: 7, h: 34 }} dashed />
          <div className="absolute inset-x-0 bottom-0 bg-[linear-gradient(0deg,var(--color-bg),transparent)] px-5 py-[18px] text-[13px] text-neutral-300">
            Tìm người trong dữ liệu camera đã phân tích — bằng ảnh, mô tả hoặc thuộc tính.
          </div>
        </SceneFrame>
      </div>
    </div>
  )
}
