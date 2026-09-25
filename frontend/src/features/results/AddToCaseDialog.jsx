import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Tag } from '@/components/ui/Tag'
import { useAppStore, useToast } from '@/store/hooks'

export function AddToCaseDialog({ result, onClose }) {
  const { me, cases, addToCase, log } = useAppStore()
  const toast = useToast()
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const own = cases.filter((c) => c.owner === me.id)

  const save = () => {
    if (!selected) return setError('Chọn một Case.')
    const target = cases.find((c) => c.id === selected)
    if (target.items.some((i) => i.rid === result.id)) {
      return setError('Kết quả này đã có trong Case đã chọn.')
    }
    addToCase(selected, result.id, result.score)
    log('Case', 'Thêm kết quả vào Case', selected)
    toast(`Đã thêm kết quả vào ${selected}.`)
    onClose()
  }

  return (
    <Dialog
      title="Thêm vào Case đã có"
      width={480}
      onClose={onClose}
      className="z-[60]"
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          <Button variant="primary" onClick={save}>
            Thêm vào Case
          </Button>
        </>
      }
    >
      <div className="text-xs text-neutral-400">Chỉ hiển thị các Case do bạn phụ trách.</div>
      <div className="flex max-h-80 flex-col gap-1.5 overflow-auto">
        {own.map((c) => (
          <label key={c.id} className="radio items-start rounded-md bg-bg px-3 py-2.5">
            <input
              type="radio"
              name="add-case"
              checked={selected === c.id}
              onChange={() => {
                setSelected(c.id)
                setError(null)
              }}
            />
            <span className="dot mt-0.5" />
            <span className="flex-1">
              <span className="block text-[13px]">{c.title}</span>
              <span className="block text-[11px] text-neutral-400">
                {c.id} · {c.items.length} kết quả
              </span>
            </span>
            {c.items.some((i) => i.rid === result.id) && <Tag>Đã có</Tag>}
          </label>
        ))}
        {!own.length && (
          <div className="text-[13px] text-neutral-400">
            Bạn chưa phụ trách Case nào. Hãy tạo Case mới.
          </div>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
    </Dialog>
  )
}
