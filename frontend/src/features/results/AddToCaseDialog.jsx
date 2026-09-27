import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Spinner } from '@/components/ui/Spinner'
import { Tag } from '@/components/ui/Tag'
import { casesApi } from '@/services/api/cases'
import { useToast } from '@/store/hooks'
import { MarkCompleteOption } from './MarkCompleteOption'

export function AddToCaseDialog({ result, onClose }) {
  const toast = useToast()
  const [own, setOwn] = useState(null)
  const [selected, setSelected] = useState(null)
  const [duplicate, setDuplicate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [complete, setComplete] = useState(false)

  useEffect(() => {
    let active = true
    casesApi
      .list({ limit: 100, status: 'OPEN' })
      .then((page) => active && setOwn(page.items))
      .catch((requestError) => {
        if (!active) return
        setOwn([])
        setError(requestError.message)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selected) return undefined
    let active = true
    casesApi
      .get(selected)
      .then(
        (detail) =>
          active && setDuplicate(detail.results.some((item) => item.track === result.track)),
      )
      .catch(() => {})
    return () => {
      active = false
    }
  }, [selected, result.track])

  const save = async () => {
    if (!selected) return setError('Chọn một vụ việc.')
    setSaving(true)
    try {
      await casesApi.addResult(selected, result.track)
      const target = own.find((c) => c.id === selected)
      const code = target?.code ?? ''
      const closeError = complete ? await casesApi.markCompleted(selected) : null
      if (closeError) {
        toast(
          `Đã thêm kết quả vào vụ việc ${code} nhưng chưa đánh dấu hoàn thành: ${closeError}`,
          'warn',
        )
      } else {
        toast(
          complete
            ? `Đã thêm kết quả và đánh dấu vụ việc ${code} hoàn thành.`
            : `Đã thêm kết quả vào vụ việc ${code}.`,
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
      title="Thêm vào vụ việc đã có"
      width={480}
      onClose={onClose}
      className="z-[60]"
      actions={
        <>
          <Button onClick={onClose}>Hủy</Button>
          <Button variant="primary" onClick={save} disabled={saving || !own?.length}>
            Thêm vào vụ việc
          </Button>
        </>
      }
    >
      <div className="text-xs text-neutral-400">
        Chỉ hiển thị các vụ việc đang xử lý do bạn phụ trách. Vụ việc đã hoàn thành cần được mở lại
        trước khi thêm kết quả.
      </div>
      <div className="flex max-h-80 flex-col gap-1.5 overflow-auto">
        {own === null && <Spinner className="text-neutral-400" />}
        {own?.map((c) => (
          <label key={c.id} className="radio items-start rounded-md bg-bg px-3 py-2.5">
            <input
              type="radio"
              name="add-case"
              checked={selected === c.id}
              onChange={() => {
                setSelected(c.id)
                setDuplicate(false)
                setError(null)
              }}
            />
            <span className="dot mt-0.5" />
            <span className="flex-1">
              <span className="block text-[13px]">{c.title}</span>
              <span className="block text-[11px] text-neutral-400">
                {c.code} · {c.resultCount} kết quả
              </span>
            </span>
            {selected === c.id && duplicate && <Tag>Đã có</Tag>}
          </label>
        ))}
        {own?.length === 0 && !error && (
          <div className="text-[13px] text-neutral-400">
            Bạn không có vụ việc nào đang xử lý. Hãy tạo vụ việc mới.
          </div>
        )}
      </div>
      {duplicate && (
        <div className="text-xs text-neutral-400">
          Kết quả này đã có trong vụ việc đã chọn. Thêm lần nữa sẽ lưu một bản mới.
        </div>
      )}
      {own?.length > 0 && <MarkCompleteOption checked={complete} onChange={setComplete} />}
      {error && <Alert>{error}</Alert>}
    </Dialog>
  )
}
