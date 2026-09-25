import {
  CheckCircleIcon,
  PlugsConnectedIcon,
  PlugsIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { SelectField, TextField } from '@/components/ui/Form'
import { Spinner } from '@/components/ui/Spinner'
import { TONE } from '@/constants/status'
import { AREAS } from '@/mocks/areas'
import { isRtspReachable } from '@/mocks/cameras'
import { useAppStore, useToast } from '@/store/hooks'
import { wait } from '@/utils/format'

const AREA_OPTIONS = AREAS.map((label, i) => ({ value: String(i), label }))

const TEST_STATE = {
  idle: {
    icon: PlugsIcon,
    color: 'var(--color-neutral-400)',
    msg: 'Chưa kiểm tra kết nối RTSP. Hệ thống sẽ thử kết nối khi lưu.',
  },
  kept: {
    icon: PlugsConnectedIcon,
    color: 'var(--color-neutral-400)',
    msg: 'Giữ cấu hình kết nối hiện tại. Đổi địa chỉ RTSP sẽ yêu cầu kiểm tra lại.',
  },
  testing: { icon: Spinner, color: 'var(--color-accent)', msg: 'Đang thử kết nối tới luồng RTSP…' },
  ok: {
    icon: CheckCircleIcon,
    color: TONE.ok,
    msg: 'Kết nối thành công · H.264 1920×1080 · 25 fps',
  },
  fail: {
    icon: WarningCircleIcon,
    color: TONE.err,
    msg: 'Không thể kết nối: hết thời gian chờ sau 10s. Kiểm tra địa chỉ, thông tin xác thực, trạng thái camera hoặc mạng.',
  },
}

const emptyForm = { name: '', area: '', rtsp: '', user: '', pass: '' }

export function CameraDialog({ camera, onClose }) {
  const { cameras, addCamera, updateCamera, log } = useAppStore()
  const toast = useToast()
  const isEdit = Boolean(camera)
  const [form, setForm] = useState(() =>
    camera
      ? {
          name: camera.name,
          area: String(camera.area),
          rtsp: camera.rtsp,
          user: 'svc_cam',
          pass: '',
        }
      : emptyForm,
  )
  const [test, setTest] = useState(isEdit ? 'kept' : 'idle')
  const [error, setError] = useState(null)

  const set = (key) => (e) => {
    const v = e.target.value
    setForm((f) => ({ ...f, [key]: v }))
    setError(null)
    if (key === 'rtsp') setTest(isEdit && v === camera.rtsp ? 'kept' : 'idle')
  }

  const validate = () => {
    if (!form.name.trim() || form.area === '') {
      return 'Vui lòng nhập tên camera và chọn khu vực lắp đặt.'
    }
    if (!/^rtsp:\/\/\S+$/.test(form.rtsp.trim())) {
      return 'Địa chỉ RTSP không đúng định dạng (rtsp://host:port/path).'
    }
    if (cameras.some((c) => c.rtsp === form.rtsp.trim() && c.id !== camera?.id)) {
      return 'Địa chỉ RTSP này đã được đăng ký cho một camera khác.'
    }
    return null
  }

  const runTest = async () => {
    const err = validate()
    if (err) {
      setError(err)
      return false
    }
    setTest('testing')
    await wait(1000)
    const ok = isRtspReachable(form.rtsp)
    setTest(ok ? 'ok' : 'fail')
    return ok
  }

  const commit = (status) => {
    const name = form.name.trim()
    const base = { name, area: Number(form.area), rtsp: form.rtsp.trim() }
    if (isEdit) {
      updateCamera(camera.id, { ...base, ...(status ? { status } : {}) })
      log('Camera', 'Cập nhật camera', name)
      toast(`Đã cập nhật ${name}.`)
    } else {
      const online = status === 'online'
      addCamera({
        ...base,
        status,
        ai: false,
        aiState: 'off',
        fps: online ? 25 : 0,
        bitrate: online ? '4.0 Mbps' : null,
        procFps: 0,
        latency: null,
        res: online ? '1920×1080 · H.264' : '—',
        last: online ? 'vừa xong' : '—',
      })
      log(
        'Camera',
        'Thêm camera',
        name,
        true,
        online ? undefined : 'Lưu ở trạng thái Chưa xác minh',
      )
      toast(
        online
          ? `Đã thêm ${name} · kết nối RTSP thành công.`
          : `Đã lưu ${name} ở trạng thái Chưa xác minh. Kiểm tra lại kết nối sau.`,
        online ? 'ok' : 'warn',
      )
    }
    onClose()
  }

  const save = async () => {
    const err = validate()
    if (err) return setError(err)
    const changed = !isEdit || form.rtsp.trim() !== camera.rtsp
    if (changed && test !== 'ok') {
      if (await runTest()) commit('online')
      return
    }
    commit(changed ? 'online' : null)
  }

  const saveUnverified = () => {
    const err = validate()
    if (err) return setError(err)
    commit('unverified')
  }

  const t = TEST_STATE[test]
  const testing = test === 'testing'

  return (
    <Dialog
      title={isEdit ? 'Chỉnh sửa camera' : 'Thêm camera'}
      width={520}
      onClose={onClose}
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          {test === 'fail' && (
            <Button onClick={saveUnverified}>Lưu ở trạng thái Chưa xác minh</Button>
          )}
          <Button variant="primary" onClick={save} disabled={testing}>
            {testing ? 'Đang kiểm tra…' : isEdit ? 'Lưu thay đổi' : 'Lưu camera'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2.5">
          <TextField
            label="Tên camera"
            value={form.name}
            onChange={set('name')}
            placeholder="vd. A-06 Sảnh phụ"
          />
          <SelectField
            label="Khu vực lắp đặt"
            value={form.area}
            onChange={set('area')}
            options={AREA_OPTIONS}
            placeholder="— Chọn —"
          />
        </div>
        <TextField
          label="Địa chỉ RTSP"
          value={form.rtsp}
          onChange={set('rtsp')}
          placeholder="rtsp://10.0.1.20:554/stream1"
          className="[&_input]:font-mono [&_input]:text-[13px]"
        />
        <div className="grid grid-cols-2 gap-2.5">
          <TextField
            label="Tài khoản RTSP"
            value={form.user}
            onChange={set('user')}
            autoComplete="off"
          />
          <TextField
            label="Mật khẩu RTSP"
            type="password"
            value={form.pass}
            onChange={set('pass')}
            placeholder={isEdit ? '•••••• (đã lưu an toàn)' : ''}
            autoComplete="new-password"
          />
        </div>
        <div className="flex items-center gap-2.5 rounded-md bg-bg px-3 py-2.5">
          <span style={{ color: t.color }} className="flex">
            <t.icon size={18} />
          </span>
          <span className="flex-1 text-xs">{t.msg}</span>
          <Button
            icon={PlugsConnectedIcon}
            onClick={runTest}
            disabled={testing}
            className="text-xs"
          >
            Kiểm tra kết nối
          </Button>
        </div>
        {error && <Alert>{error}</Alert>}
      </div>
    </Dialog>
  )
}
