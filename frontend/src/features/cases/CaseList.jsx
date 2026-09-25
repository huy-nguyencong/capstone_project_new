import { OptionCard } from '@/components/ui/Chip'

export function CaseList({ cases, selectedId, onSelect, metaFor, emptyText }) {
  return (
    <div className="flex flex-col gap-1.5">
      {cases.map((c) => (
        <OptionCard
          key={c.id}
          active={c.id === selectedId}
          className="gap-1"
          onClick={() => onSelect(c.id)}
        >
          <div className="flex gap-2 text-[11px] text-neutral-400">
            <span className="font-mono">{c.code}</span>
            <span className="ml-auto">{c.resultCount} kết quả</span>
          </div>
          <div className="text-sm leading-[1.35] text-pretty">{c.title}</div>
          <div className="text-[11px] text-neutral-400">{metaFor(c)}</div>
        </OptionCard>
      ))}
      {!cases.length && <div className="px-1 py-6 text-[13px] text-neutral-400">{emptyText}</div>}
    </div>
  )
}
