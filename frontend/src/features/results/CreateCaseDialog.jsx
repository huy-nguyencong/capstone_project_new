import { UserFocusIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { useAppStore, useToast } from '@/store/hooks'

export function CreateCaseDialog({ result, onClose }) {
  const { me, createCase, log } = useAppStore()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState(null)

  const save = () => {
    if (!title.trim()) return setError('Vui lòng nhập tiêu đề Case.')
    const id = createCase({
      title: title.trim(),
      note: note.trim(),
      rid: result.id,
      score: result.score,
    })
    log('Case', 'Tạo Case', id)
    toast(`Đã tạo ${id} với kết quả đã chọn.`)
    onClose()
  }

  return (
    <Dialog
      title="Tạo Case mới"
      width={480}
      onClose={onClose}
      className="z-[60]"
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          <Button variant="primary" onClick={save}>
            Tạo Case
          </Button>
        </>
      }
    >
      <div className="flex items-center gap-2.5 rounded-md bg-bg px-3 py-2.5 text-xs">
        <UserFocusIcon size={18} className="text-accent" />
        <span className="flex-1">
          Kết quả được chọn: <span className="font-mono">{result.track}</span> · {result.camName}
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
      {error && <Alert>{error}</Alert>}
    </Dialog>
  )
}
