import { useEffect, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Spinner } from '@/components/ui/Spinner'
import { Tag } from '@/components/ui/Tag'
import { casesApi } from '@/services/api/cases'
import { useToast } from '@/store/hooks'

export function AddToCaseDialog({ result, onClose }) {
  const toast = useToast()
  const [own, setOwn] = useState(null)
  const [selected, setSelected] = useState(null)
  const [duplicate, setDuplicate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    casesApi
      .list({ limit: 100 })
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
    if (!selected) return setError('Chọn một Case.')
    setSaving(true)
    try {
      await casesApi.addResult(selected, result.track)
      const target = own.find((c) => c.id === selected)
      toast(`Đã thêm kết quả vào Case ${target?.code ?? ''}.`)
      onClose()
    } catch (requestError) {
      setError(requestError.message)
      setSaving(false)
    }
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
          <Button variant="primary" onClick={save} disabled={saving || !own?.length}>
            Thêm vào Case
          </Button>
        </>
      }
    >
      <div className="text-xs text-neutral-400">Chỉ hiển thị các Case do bạn phụ trách.</div>
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
            Bạn chưa phụ trách Case nào. Hãy tạo Case mới.
          </div>
        )}
      </div>
      {duplicate && (
        <div className="text-xs text-neutral-400">
          Kết quả này đã có trong Case đã chọn. Thêm lần nữa sẽ lưu một bản mới.
        </div>
      )}
      {error && <Alert>{error}</Alert>}
    </Dialog>
  )
}
