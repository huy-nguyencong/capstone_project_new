import { ArrowCounterClockwiseIcon, CheckCircleIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { StatusDot } from '@/components/ui/StatusDot'
import { TextAreaField, TextField } from '@/components/ui/Form'
import { Tag } from '@/components/ui/Tag'
import { CASE_STATUS } from '@/constants/status'
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
  const closed = caseFile.status === 'closed'
  // A completed Case is read-only for its owner until reopened.
  const canEdit = editable && !closed
  const dirty = title !== caseFile.title || note !== caseFile.note

  const save = async () => {
    if (!title.trim()) return toast('Tiêu đề vụ việc không được để trống.', 'err')
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
      toast(`Đã lưu thay đổi của vụ việc ${updated.code}.`)
    } catch (error) {
      toast(error.message, 'err')
    } finally {
      setSaving(false)
    }
  }

  const setStatus = (next) =>
    confirm({
      title: next === 'CLOSED' ? 'Đánh dấu vụ việc hoàn thành?' : 'Mở lại vụ việc?',
      body:
        next === 'CLOSED'
          ? 'Vụ việc sẽ bị khóa: không thêm, loại kết quả hay sửa tiêu đề, ghi chú. Bạn có thể mở lại khi cần.'
          : 'Vụ việc quay về trạng thái Đang xử lý và có thể chỉnh sửa, thêm kết quả như bình thường.',
      label: next === 'CLOSED' ? 'Đánh dấu hoàn thành' : 'Mở lại',
      onConfirm: async () => {
        try {
          const updated = await casesApi.update(caseFile.id, {
            status: next,
            version: caseFile.version,
          })
          setTitle(updated.title)
          setNote(updated.note)
          onChange({ case: updated, results })
          toast(
            next === 'CLOSED'
              ? `Vụ việc ${updated.code} đã được đánh dấu hoàn thành.`
              : `Đã mở lại vụ việc ${updated.code}.`,
          )
        } catch (error) {
          toast(error.message, 'err')
        }
      },
    })

  const discard = () => {
    setTitle(caseFile.title)
    setNote(caseFile.note)
  }

  const remove = (resultId) =>
    confirm({
      title: 'Loại kết quả khỏi vụ việc?',
      body: 'Kết quả chỉ bị loại khỏi vụ việc này. Dữ liệu kết quả gốc trong hệ thống không bị xóa.',
      label: 'Loại khỏi vụ việc',
      onConfirm: async () => {
        try {
          await casesApi.removeResult(caseFile.id, resultId)
          onChange(await casesApi.get(caseFile.id))
          toast(`Đã loại kết quả khỏi vụ việc ${caseFile.code}.`)
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
        {closed && caseFile.closed && <span>Hoàn thành: {caseFile.closed}</span>}
        <StatusDot {...CASE_STATUS[caseFile.status]} className="ml-auto text-xs" />
      </div>

      {editable && (
        <div className="flex flex-wrap items-center gap-2">
          {closed ? (
            <>
              <Alert tone="notice" className="flex-1">
                Vụ việc đã hoàn thành và đang bị khóa. Mở lại để chỉnh sửa hoặc thêm kết quả.
              </Alert>
              <Button icon={ArrowCounterClockwiseIcon} onClick={() => setStatus('OPEN')}>
                Mở lại vụ việc
              </Button>
            </>
          ) : (
            <Button
              icon={CheckCircleIcon}
              className="ml-auto"
              disabled={dirty}
              onClick={() => setStatus('CLOSED')}
            >
              Đánh dấu hoàn thành
            </Button>
          )}
        </div>
      )}

      {canEdit ? (
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
          onRemove={canEdit ? remove : undefined}
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
