import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { Tag } from '@/components/ui/Tag'
import { ResultViewer } from '@/features/results/ResultViewer'
import { useAppStore, useConfirm, useToast } from '@/store/hooks'
import { CaseItemGrid } from './CaseItemGrid'

const ownerNote = (u) => {
  if (!u || u.status === 'active') return null
  return u.status === 'locked' ? 'Tài khoản đã khóa' : 'Tài khoản ngừng hoạt động'
}

export function CaseDetail({ caseFile, editable }) {
  const { users, updateCase, removeFromCase, log } = useAppStore()
  const confirm = useConfirm()
  const toast = useToast()
  const [title, setTitle] = useState(caseFile.title)
  const [note, setNote] = useState(caseFile.note)
  const [viewer, setViewer] = useState(null)

  const owner = users.find((u) => u.id === caseFile.owner)
  const note2 = ownerNote(owner)
  const dirty = title !== caseFile.title || note !== caseFile.note

  const save = () => {
    if (!title.trim()) return toast('Tiêu đề Case không được để trống.', 'err')
    updateCase(caseFile.id, { title: title.trim(), note })
    log('Case', 'Cập nhật Case', caseFile.id)
    toast(`Đã lưu thay đổi của ${caseFile.id}.`)
  }

  const discard = () => {
    setTitle(caseFile.title)
    setNote(caseFile.note)
  }

  const remove = (rid) =>
    confirm({
      title: 'Loại kết quả khỏi Case?',
      body: 'Kết quả chỉ bị loại khỏi Case này. Dữ liệu kết quả gốc trong hệ thống không bị xóa.',
      label: 'Loại khỏi Case',
      onConfirm: () => {
        removeFromCase(caseFile.id, rid)
        log('Case', 'Loại kết quả khỏi Case', caseFile.id)
        toast(`Đã loại kết quả khỏi ${caseFile.id}.`)
      },
    })

  return (
    <section className="panel flex flex-col gap-4 p-[18px]">
      <div className="flex flex-wrap gap-x-[18px] gap-y-1.5 text-xs text-neutral-400">
        <span className="font-mono text-accent-300">{caseFile.id}</span>
        <span>
          Phụ trách: <span className="text-text">{owner?.name ?? '—'}</span>
        </span>
        {note2 && <Tag>{note2}</Tag>}
        <span>Tạo: {caseFile.created}</span>
        <span>Cập nhật: {caseFile.updated}</span>
      </div>

      {editable ? (
        <>
          <TextField label="Tiêu đề" value={title} onChange={(e) => setTitle(e.target.value)} />
          <TextAreaField label="Ghi chú" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button onClick={discard} disabled={!dirty}>
              Hủy thay đổi
            </Button>
            <Button variant="primary" onClick={save} disabled={!dirty}>
              Lưu thay đổi
            </Button>
          </div>
        </>
      ) : (
        <div>
          <h3 className="mb-2 text-[21px]">{caseFile.title}</h3>
          <p className="m-0 max-w-[720px] text-sm text-pretty text-neutral-200">{caseFile.note}</p>
        </div>
      )}

      <div>
        <div className="mb-2.5 flex items-center gap-2">
          <h5 className="m-0">Kết quả đã lưu</h5>
          <span className="text-xs text-neutral-400">{caseFile.items.length} kết quả</span>
        </div>
        <CaseItemGrid
          items={caseFile.items}
          onOpen={(items, index) => setViewer({ items, index })}
          onRemove={editable ? remove : undefined}
        />
      </div>

      {viewer && (
        <ResultViewer
          items={viewer.items}
          index={viewer.index}
          context={editable ? 'case-op' : 'case-viewer'}
          onIndexChange={(index) => setViewer((v) => ({ ...v, index }))}
          onClose={() => setViewer(null)}
        />
      )}
    </section>
  )
}
