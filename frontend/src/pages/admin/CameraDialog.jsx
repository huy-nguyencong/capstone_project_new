import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { SelectField, TextField } from '@/components/ui/Form'
import { camerasApi } from '@/services/api/cameras'
import { usersApi } from '@/services/api/users'
import { useToast } from '@/store/hooks'

export function CameraDialog({ camera, onClose, onSaved }) {
  const toast = useToast()
  const [areas, setAreas] = useState([])
  const [form, setForm] = useState({
    code: camera?.code || '',
    name: camera?.name || '',
    area_id: camera?.area.id || '',
    rtsp_url: '',
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [replaceRtsp, setReplaceRtsp] = useState(false)
  useEffect(() => {
    let live = true
    usersApi
      .areas()
      .then((items) => {
        if (live) setAreas(items)
      })
      .catch((e) => {
        if (live) setError(e.message)
      })
    return () => {
      live = false
    }
  }, [])
  const field = (key) => (e) => setForm((old) => ({ ...old, [key]: e.target.value }))
  const save = async (test = false) => {
    setBusy(true)
    setError(null)
    let saved
    try {
      const body = camera ? { name: form.name, version: camera.version } : { ...form }
      if (camera && replaceRtsp) body.rtsp_url = form.rtsp_url || null
      saved = camera ? await camerasApi.update(camera.id, body) : await camerasApi.create(body)
      if (test && saved.hasRtsp) {
        try {
          const result = await camerasApi.test(saved.id)
          toast(result.message, result.rtsp_status === 'ONLINE' ? 'ok' : 'warn')
        } catch (e) {
          toast(`Đã lưu camera. Kiểm tra kết nối: ${e.message}`, 'warn')
        }
      } else toast('Đã lưu camera.')
      onSaved()
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog
      title={camera ? 'Chỉnh sửa camera' : 'Thêm camera'}
      width={520}
      onClose={busy ? undefined : onClose}
      actions={
        <>
          <Button onClick={onClose} disabled={busy}>
            Hủy
          </Button>
          <Button
            onClick={() => save(true)}
            disabled={busy || !(form.rtsp_url || (camera?.hasRtsp && !replaceRtsp))}
          >
            Lưu và kiểm tra RTSP
          </Button>
          <Button variant="primary" onClick={() => save()} disabled={busy}>
            {busy ? 'Đang lưu…' : 'Lưu camera'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <TextField
          label="Mã camera"
          value={form.code}
          onChange={field('code')}
          disabled={Boolean(camera) || busy}
        />
        <TextField label="Tên camera" value={form.name} onChange={field('name')} disabled={busy} />
        <SelectField
          label="Khu vực"
          value={form.area_id}
          onChange={field('area_id')}
          options={areas.map((a) => ({ value: a.id, label: a.name }))}
          placeholder="— Chọn —"
          disabled={Boolean(camera) || busy}
        />
        {camera && (
          <>
            <p className="text-muted text-xs">RTSP hiện tại: {camera.rtsp || 'Không có'}</p>
            <label className="text-sm">
              <input
                type="checkbox"
                checked={replaceRtsp}
                disabled={busy}
                onChange={(e) => setReplaceRtsp(e.target.checked)}
              />{' '}
              Thay địa chỉ RTSP
            </label>
          </>
        )}
        {(!camera || replaceRtsp) && (
          <TextField
            label="RTSP (tùy chọn; để trống nếu chỉ dùng video)"
            value={form.rtsp_url}
            onChange={field('rtsp_url')}
            disabled={busy}
            autoComplete="off"
            placeholder="rtsp://user:password@10.0.1.20:554/stream1"
          />
        )}
        {error && <Alert>{error}</Alert>}
      </div>
    </Dialog>
  )
}
