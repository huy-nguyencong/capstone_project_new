import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, SelectField, TextField } from '@/components/ui/Form'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { usersApi } from '@/services/api/users'
import { useToast } from '@/store/hooks'

const ROLE_OPTIONS = [
  { value: 'operator', label: 'Operator' },
  { value: 'viewer', label: 'Viewer' },
]

const emptyForm = { name: '', username: '', password: '', role: 'operator', areaId: '' }

const toForm = (user) => ({
  name: user.name,
  username: user.username,
  password: '',
  role: user.role,
  areaId: user.area?.id ?? '',
})

export function UserDialog({ user, areas, onClose, onSaved }) {
  const toast = useToast()
  const isEdit = Boolean(user)
  const [currentUser, setCurrentUser] = useState(user)
  const [form, setForm] = useState(() => (user ? toForm(user) : emptyForm))
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!user) return undefined
    let active = true
    usersApi
      .get(user.id)
      .then((fresh) => {
        if (!active) return
        setCurrentUser(fresh)
        setForm(toForm(fresh))
      })
      .catch((requestError) => active && setError(requestError.message))
    return () => {
      active = false
    }
  }, [user])

  const set = (key) => (event) => {
    setForm((value) => ({ ...value, [key]: event.target.value }))
    setError(null)
  }

  const validate = () => {
    if (!form.name.trim() || !form.username.trim()) {
      return 'Vui lòng nhập đầy đủ họ tên và tên đăng nhập.'
    }
    if (!/^[a-z0-9._]{3,32}$/.test(form.username)) {
      return 'Tên đăng nhập chỉ gồm chữ thường, số, dấu chấm hoặc gạch dưới (3–32 ký tự).'
    }
    if ((!isEdit || form.password) && form.password.length < 8) {
      return 'Mật khẩu tối thiểu 8 ký tự.'
    }
    if (form.role === 'operator' && !form.areaId) {
      return 'Operator phải được gán đúng một khu vực giám sát.'
    }
    return null
  }

  const save = async () => {
    const validationMessage = validate()
    if (validationMessage) {
      setError(validationMessage)
      return
    }
    setSaving(true)
    setError(null)
    const payload = {
      display_name: form.name.trim(),
      role: form.role.toUpperCase(),
      area_id: form.role === 'operator' ? form.areaId : null,
    }
    if (form.password) payload.password = form.password
    try {
      const saved = isEdit
        ? await usersApi.update(user.id, { ...payload, version: currentUser.version })
        : await usersApi.create({
            ...payload,
            username: form.username.trim(),
            password: form.password,
          })
      toast(
        isEdit ? `Đã cập nhật tài khoản ${saved.username}.` : `Đã tạo tài khoản ${saved.username}.`,
      )
      onSaved(saved)
      onClose()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const areaOptions = areas.map((area) => ({
    value: area.id,
    label: `${area.code} · ${area.name}`,
  }))

  return (
    <Dialog
      title={isEdit ? 'Chỉnh sửa tài khoản' : 'Tạo tài khoản'}
      width={480}
      onClose={onClose}
      actions={
        <>
          <Button onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            {saving ? 'Đang lưu…' : isEdit ? 'Lưu thay đổi' : 'Tạo tài khoản'}
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
          disabled={isEdit}
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
              setForm((value) => ({
                ...value,
                role,
                areaId: role === 'viewer' ? '' : value.areaId,
              }))
              setError(null)
            }}
          />
        </Field>
        {form.role === 'operator' ? (
          <SelectField
            label="Khu vực giám sát (chọn đúng một)"
            value={form.areaId}
            onChange={set('areaId')}
            options={areaOptions}
            placeholder="— Chọn khu vực —"
          />
        ) : (
          <div className="text-xs text-neutral-400">
            Viewer xem được toàn bộ Case ở chế độ chỉ đọc và không được gán khu vực.
          </div>
        )}
        {error && <Alert>{error}</Alert>}
      </div>
    </Dialog>
  )
}
