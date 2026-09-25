import {
  CaretLeftIcon,
  CaretRightIcon,
  EyeIcon,
  FolderPlusIcon,
  FolderSimplePlusIcon,
  XIcon,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button, IconButton } from '@/components/ui/Button'
import { KeyValueList } from '@/components/ui/Panel'
import { PersonCrop } from '@/components/person/PersonCrop'
import { ResultScene } from '@/components/person/SceneFrame'
import { AddToCaseDialog } from './AddToCaseDialog'
import { CreateCaseDialog } from './CreateCaseDialog'

const KICKER = {
  search: 'Kết quả tìm kiếm',
  'case-op': 'Kết quả trong Case',
  'case-viewer': 'Kết quả đã lưu',
}

export function ResultViewer({ items, index, context, onIndexChange, onClose }) {
  const [dialog, setDialog] = useState(null)
  const result = items[index]
  const hasPrev = index > 0
  const hasNext = index < items.length - 1

  useEffect(() => {
    if (dialog) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft' && hasPrev) onIndexChange(index - 1)
      if (e.key === 'ArrowRight' && hasNext) onIndexChange(index + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialog, hasPrev, hasNext, index, onClose, onIndexChange])

  const meta = [
    { k: 'Camera', v: result.camName },
    { k: 'Khu vực', v: result.area },
    { k: 'Thời gian', v: result.when },
    { k: 'Track', v: result.track, mono: true },
    ...(result.saved ? [{ k: 'Lưu vào Case', v: result.saved }] : []),
  ]

  return createPortal(
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 grid place-items-center bg-[color-mix(in_srgb,var(--color-neutral-900)_72%,transparent)] p-6"
      >
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Track ${result.track}`}
          onClick={(e) => e.stopPropagation()}
          className="flex max-h-[calc(100vh-48px)] w-[min(1120px,100%)] flex-col gap-3.5 overflow-auto rounded-lg bg-surface p-[18px] shadow-lg"
        >
          <div className="flex items-center gap-2.5">
            <div className="min-w-0 flex-1">
              <div className="kicker text-accent-300">{KICKER[context]}</div>
              <div className="text-lg font-medium">Track {result.track}</div>
            </div>
            <span className="text-xs text-neutral-400">
              {index + 1} / {items.length}
            </span>
            <IconButton
              icon={CaretLeftIcon}
              label="Kết quả trước"
              variant="secondary"
              disabled={!hasPrev}
              onClick={() => onIndexChange(index - 1)}
            />
            <IconButton
              icon={CaretRightIcon}
              label="Kết quả tiếp theo"
              variant="secondary"
              disabled={!hasNext}
              onClick={() => onIndexChange(index + 1)}
            />
            <IconButton icon={XIcon} label="Đóng" onClick={onClose} />
          </div>

          <div className="grid items-start gap-[18px] md:grid-cols-[minmax(0,1fr)_260px]">
            <div className="flex flex-col gap-2">
              <ResultScene result={result} />
              <div className="text-[11px] text-neutral-500">
                Frame toàn cảnh đại diện của track · bounding box vẽ từ dữ liệu đã lưu
              </div>
            </div>

            <div className="flex flex-col gap-3.5">
              <div className="flex items-end gap-3">
                <div className="w-[84px] flex-none">
                  <PersonCrop result={result} showScore={false} />
                </div>
                {result.scoreText && (
                  <div>
                    <div className="text-[11px] text-neutral-400">Điểm phù hợp</div>
                    <div className="text-[30px] leading-[1.1] font-medium text-accent-200">
                      {result.scoreText}
                    </div>
                  </div>
                )}
              </div>
              <KeyValueList items={meta} />
              {result.scoreText && (
                <p className="m-0 text-xs text-pretty text-neutral-400">
                  Điểm phù hợp chỉ hỗ trợ xếp hạng; người dùng cần quan sát ảnh để xác định kết quả.
                </p>
              )}
              {context === 'search' && (
                <div className="flex flex-col gap-1.5">
                  <Button
                    variant="primary"
                    icon={FolderPlusIcon}
                    className="h-9"
                    onClick={() => setDialog('create')}
                  >
                    Tạo Case mới
                  </Button>
                  <Button
                    icon={FolderSimplePlusIcon}
                    className="h-9"
                    onClick={() => setDialog('add')}
                  >
                    Thêm vào Case đã có
                  </Button>
                </div>
              )}
              {context === 'case-viewer' && (
                <div className="flex items-center gap-1.5 text-xs text-neutral-400">
                  <EyeIcon size={14} />
                  Chế độ chỉ xem
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {dialog === 'create' && <CreateCaseDialog result={result} onClose={() => setDialog(null)} />}
      {dialog === 'add' && <AddToCaseDialog result={result} onClose={() => setDialog(null)} />}
    </>,
    document.body,
  )
}
