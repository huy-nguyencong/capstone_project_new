import { WarningIcon, XIcon } from '@phosphor-icons/react'
import { IconButton } from '@/components/ui/Button'
import { PersonCrop } from '@/components/person/PersonCrop'
import { findDetection } from '@/mocks/detections'
import { useAppStore } from '@/store/hooks'
import { describeResult } from '@/utils/results'

export function CaseItemGrid({ items, onOpen, onRemove }) {
  const { cameras } = useAppStore()
  const available = items.filter((i) => findDetection(i.rid))

  if (!items.length) {
    return <div className="py-3.5 text-[13px] text-neutral-400">Case chưa có kết quả nào.</div>
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
      {items.map((item) => {
        const det = findDetection(item.rid)
        if (!det) {
          return (
            <div key={item.rid} className="flex flex-col gap-2 rounded-md bg-bg p-2 shadow-sm">
              <div className="grid aspect-[3/5] place-items-center rounded-md border border-dashed border-neutral-700 p-2.5 text-center text-[11px] text-neutral-400">
                <div className="flex flex-col items-center gap-1">
                  <WarningIcon size={20} />
                  <div>Kết quả không còn khả dụng</div>
                </div>
              </div>
              <div className="text-[11px] text-neutral-500">Lưu lúc {item.saved}</div>
            </div>
          )
        }
        const result = describeResult(det, cameras, item.score)
        const index = available.findIndex((a) => a.rid === item.rid)
        return (
          <div
            key={item.rid}
            className="relative flex flex-col gap-2 rounded-md bg-bg p-2 shadow-sm"
          >
            <button
              type="button"
              onClick={() => onOpen(available, index)}
              className="block rounded-md border-0 bg-transparent p-0"
              aria-label={`Xem track ${result.track}`}
            >
              <PersonCrop result={result} />
            </button>
            <div className="min-w-0">
              <div className="truncate text-xs">{result.camName}</div>
              <div className="text-[11px] text-neutral-400">{result.when}</div>
            </div>
            {onRemove && (
              <IconButton
                icon={XIcon}
                size={13}
                label="Loại khỏi Case"
                onClick={() => onRemove(item.rid)}
                className="absolute top-3 right-3 size-[26px] bg-[color-mix(in_srgb,var(--color-bg)_80%,transparent)]"
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
