import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, SelectField, TextField } from '@/components/ui/Form'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { AREAS } from '@/mocks/areas'
import { useAppStore, useToast } from '@/store/hooks'

const AREA_OPTIONS = AREAS.map((label, i) => ({ value: String(i), label }))

const ROLE_OPTIONS = [
  { value: 'operator', label: 'Operator' },
  { value: 'viewer', label: 'Viewer' },
]

const emptyForm = { name: '', username: '', password: '', role: 'operator', area: '' }

const toForm = (u) => ({
  name: u.name,
  username: u.username,
  password: '',
  role: u.role,
  area: u.area == null ? '' : String(u.area),
})

export function UserDialog({ user, onClose }) {
  const { users, addUser, updateUser, log } = useAppStore()
  const toast = useToast()
  const isEdit = Boolean(user)
  const [form, setForm] = useState(() => (user ? toForm(user) : emptyForm))
  const [error, setError] = useState(null)

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setError(null)
  }

  const validate = () => {
    if (!form.name.trim() || !form.username.trim()) {
      return 'Vui lòng nhập đầy đủ họ tên và tên đăng nhập.'
    }
    if (!/^[a-z0-9._]{3,32}$/.test(form.username)) {
      return 'Tên đăng nhập chỉ gồm chữ thường, số, dấu chấm hoặc gạch dưới (3–32 ký tự).'
    }
    if ((!isEdit || form.password) && form.password.length < 8) return 'Mật khẩu tối thiểu 8 ký tự.'
    if (users.some((u) => u.username === form.username && u.id !== user?.id)) {
      return 'Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.'
    }
    if (form.role === 'operator' && form.area === '') {
      return 'Operator phải được gán đúng một khu vực giám sát.'
    }
    return null
  }

  const save = () => {
    const err = validate()
    if (err) return setError(err)
    const area = form.role === 'operator' ? Number(form.area) : null
    const data = { name: form.name.trim(), username: form.username, role: form.role, area }
    if (isEdit) {
      updateUser(user.id, data)
      const action =
        user.role !== form.role
          ? 'Thay đổi vai trò'
          : user.area !== area
            ? 'Thay đổi khu vực giám sát'
            : 'Cập nhật tài khoản'
      log('Tài khoản', action, form.username)
      toast(`Đã cập nhật tài khoản ${form.username}.`)
    } else {
      addUser(data)
      log('Tài khoản', 'Tạo tài khoản', form.username)
      toast(`Đã tạo tài khoản ${form.username}.`)
    }
    onClose()
  }

  return (
    <Dialog
      title={isEdit ? 'Chỉnh sửa tài khoản' : 'Tạo tài khoản'}
      width={480}
      onClose={onClose}
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          <Button variant="primary" onClick={save}>
            {isEdit ? 'Lưu thay đổi' : 'Tạo tài khoản'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <TextField label="Họ tên" value={form.name} onChange={set('name')} />
        <TextField
          label="Tên đăng nhập"
          value={form.username}
          onChange={set('username')}
          placeholder="vd. minh.le"
        />
        <TextField
          label={isEdit ? 'Mật khẩu mới (để trống nếu không đổi)' : 'Mật khẩu'}
          type="password"
          value={form.password}
          onChange={set('password')}
          placeholder="Tối thiểu 8 ký tự"
          autoComplete="new-password"
        />
        <Field label="Vai trò">
          <SegmentedControl
            options={ROLE_OPTIONS}
            value={form.role}
            onChange={(role) => {
              setForm((f) => ({ ...f, role }))
              setError(null)
            }}
          />
        </Field>
        {form.role === 'operator' ? (
          <SelectField
            label="Khu vực giám sát (chọn đúng một)"
            value={form.area}
            onChange={set('area')}
            options={AREA_OPTIONS}
            placeholder="— Chọn khu vực —"
          />
        ) : (
          <div className="text-xs text-neutral-400">
            Viewer xem được toàn bộ Case trên hệ thống ở chế độ chỉ đọc, không gắn khu vực.
          </div>
        )}
        {error && <Alert>{error}</Alert>}
      </div>
    </Dialog>
  )
}
