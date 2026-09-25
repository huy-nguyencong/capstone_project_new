import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { Tag } from '@/components/ui/Tag'
import { ResultViewer } from '@/features/results/ResultViewer'
import { casesApi } from '@/services/api/cases'
import { useConfirm, useToast } from '@/store/hooks'
import { CaseItemGrid } from './CaseItemGrid'

const OWNER_NOTE = {
  locked: 'Tài khoản đã khóa',
  inactive: 'Tài khoản ngừng hoạt động',
  deleted: 'Tài khoản đã xóa',
}

export function CaseDetail({ detail, editable, onChange }) {
  const { case: caseFile, results } = detail
  const confirm = useConfirm()
  const toast = useToast()
  const [title, setTitle] = useState(caseFile.title)
  const [note, setNote] = useState(caseFile.note)
  const [saving, setSaving] = useState(false)
  const [viewerIndex, setViewerIndex] = useState(null)

  const ownerNote = OWNER_NOTE[caseFile.owner.status]
  const dirty = title !== caseFile.title || note !== caseFile.note

  const save = async () => {
    if (!title.trim()) return toast('Tiêu đề Case không được để trống.', 'err')
    setSaving(true)
    try {
      const updated = await casesApi.update(caseFile.id, {
        title: title.trim(),
        note: note.trim() || null,
        version: caseFile.version,
      })
      setTitle(updated.title)
      setNote(updated.note)
      onChange({ case: updated, results })
      toast(`Đã lưu thay đổi của Case ${updated.code}.`)
    } catch (error) {
      toast(error.message, 'err')
    } finally {
      setSaving(false)
    }
  }

  const discard = () => {
    setTitle(caseFile.title)
    setNote(caseFile.note)
  }

  const remove = (resultId) =>
    confirm({
      title: 'Loại kết quả khỏi Case?',
      body: 'Kết quả chỉ bị loại khỏi Case này. Dữ liệu kết quả gốc trong hệ thống không bị xóa.',
      label: 'Loại khỏi Case',
      onConfirm: async () => {
        try {
          await casesApi.removeResult(caseFile.id, resultId)
          onChange(await casesApi.get(caseFile.id))
          toast(`Đã loại kết quả khỏi Case ${caseFile.code}.`)
        } catch (error) {
          toast(error.message, 'err')
        }
      },
    })

  return (
    <section className="panel flex flex-col gap-4 p-[18px]">
      <div className="flex flex-wrap gap-x-[18px] gap-y-1.5 text-xs text-neutral-400">
        <span className="font-mono text-accent-300" title={caseFile.id}>
          {caseFile.code}
        </span>
        <span>
          Phụ trách: <span className="text-text">{caseFile.owner.name}</span>
        </span>
        {ownerNote && <Tag>{ownerNote}</Tag>}
        <span>Tạo: {caseFile.created}</span>
        <span>Cập nhật: {caseFile.updated}</span>
      </div>

      {editable ? (
        <>
          <TextField label="Tiêu đề" value={title} onChange={(e) => setTitle(e.target.value)} />
          <TextAreaField label="Ghi chú" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button onClick={discard} disabled={!dirty || saving}>
              Hủy thay đổi
            </Button>
            <Button variant="primary" onClick={save} disabled={!dirty || saving}>
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
          <span className="text-xs text-neutral-400">{results.length} kết quả</span>
        </div>
        <CaseItemGrid
          items={results}
          onOpen={setViewerIndex}
          onRemove={editable ? remove : undefined}
        />
      </div>

      {viewerIndex != null && results[viewerIndex] && (
        <ResultViewer
          items={results}
          index={viewerIndex}
          context={editable ? 'case-op' : 'case-viewer'}
          onIndexChange={setViewerIndex}
          onClose={() => setViewerIndex(null)}
        />
      )}
    </section>
  )
}
