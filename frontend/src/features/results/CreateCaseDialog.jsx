import { UserFocusIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { casesApi } from '@/services/api/cases'
import { useAppStore, useToast } from '@/store/hooks'
import { MarkCompleteOption } from './MarkCompleteOption'

export function CreateCaseDialog({ result, onClose }) {
  const { me } = useAppStore()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [complete, setComplete] = useState(false)

  const save = async () => {
    if (!title.trim()) return setError('Vui lòng nhập tiêu đề vụ việc.')
    setSaving(true)
    try {
      const created = await casesApi.create({
        title: title.trim(),
        note: note.trim() || null,
        track_id: result.track,
      })
      const closeError = complete ? await casesApi.markCompleted(created.case.id) : null
      if (closeError) {
        toast(
          `Đã tạo vụ việc ${created.case.code} nhưng chưa đánh dấu hoàn thành: ${closeError}`,
          'warn',
        )
      } else {
        toast(
          complete
            ? `Đã tạo vụ việc ${created.case.code} và đánh dấu hoàn thành.`
            : `Đã tạo vụ việc ${created.case.code} với kết quả đã chọn.`,
        )
      }
      onClose()
    } catch (requestError) {
      setError(requestError.message)
      setSaving(false)
    }
  }

  return (
    <Dialog
      title="Tạo vụ việc mới"
      width={480}
      onClose={onClose}
      className="z-[60]"
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            Tạo vụ việc
          </Button>
        </>
      }
    >
      <div className="flex items-center gap-2.5 rounded-md bg-bg px-3 py-2.5 text-xs">
        <UserFocusIcon size={18} className="text-accent" />
        <span className="flex-1">
          Kết quả được chọn: {result.camName} · {result.when}
        </span>
        <span className="text-accent-200">{result.scoreText}</span>
      </div>
      <TextField
        label="Tiêu đề"
        value={title}
        onChange={(e) => {
          setTitle(e.target.value)
          setError(null)
        }}
        placeholder="vd. Tìm người để quên hành lý"
      />
      <TextAreaField label="Ghi chú" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="text-xs text-neutral-400">
        Người phụ trách: {me.name} (tự động theo tài khoản đang đăng nhập)
      </div>
      <MarkCompleteOption checked={complete} onChange={setComplete} />
      {error && <Alert>{error}</Alert>}
    </Dialog>
  )
}
