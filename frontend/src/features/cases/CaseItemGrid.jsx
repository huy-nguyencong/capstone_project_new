import { XIcon } from '@phosphor-icons/react'
import { IconButton } from '@/components/ui/Button'
import { PersonCrop } from '@/components/person/PersonCrop'

export function CaseItemGrid({ items, onOpen, onRemove }) {
  if (!items.length) {
    return <div className="py-3.5 text-[13px] text-neutral-400">Vụ việc chưa có kết quả nào.</div>
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
      {items.map((item, index) => (
        <div key={item.id} className="relative flex flex-col gap-2 rounded-md bg-bg p-2 shadow-sm">
          <button
            type="button"
            onClick={() => onOpen(index)}
            className="block rounded-md border-0 bg-transparent p-0"
            aria-label={`Xem kết quả tại ${item.camName} lúc ${item.when}`}
          >
            <PersonCrop result={item} />
          </button>
          <div className="min-w-0">
            <div className="truncate text-xs">{item.camName}</div>
            <div className="text-[11px] text-neutral-400">{item.when}</div>
            <div className="text-[11px] text-neutral-500">Lưu lúc {item.saved}</div>
          </div>
          {onRemove && (
            <IconButton
              icon={XIcon}
              size={13}
              label="Loại khỏi vụ việc"
              onClick={() => onRemove(item.id)}
              className="absolute top-3 right-3 size-[26px] bg-[color-mix(in_srgb,var(--color-bg)_80%,transparent)]"
            />
          )}
        </div>
      ))}
    </div>
  )
}
