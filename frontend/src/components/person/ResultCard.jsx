import { cx } from '@/components/ui/cx'
import { PersonCrop } from './PersonCrop'

// Overview card: image + rank to scan, camera + time to compare. Area and date are shown once
// in the results header; the score stays as secondary text (full detail in the viewer).
export function ResultCard({ result, rank, showDate, onOpen }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      // Drag a result into the image search box to search again from this person.
      draggable={Boolean(result.cropUrl)}
      onDragStart={(e) => {
        const url = new URL(result.cropUrl, window.location.href).href
        e.dataTransfer.setData('text/uri-list', url)
        e.dataTransfer.setData('text/plain', url)
        e.dataTransfer.effectAllowed = 'copy'
      }}
      title="Bấm để xem chi tiết · kéo vào ô Hình ảnh để tìm tiếp bằng người này"
      aria-label={`${result.camName} · ${result.when} · điểm phù hợp ${result.scoreText}`}
      className={cx(
        'flex flex-col gap-2 rounded-md border-0 bg-surface p-2 text-left text-text shadow-sm transition-shadow hover:shadow-glow',
        rank === 1 && 'ring-1 ring-accent-600',
      )}
    >
      <PersonCrop result={result} rank={rank} />
      <div className="min-w-0">
        <div className="truncate text-xs">{result.camName}</div>
        <div className="text-[11px] text-neutral-400">
          {showDate ? result.when : result.time} · Điểm {result.scoreShort}
        </div>
      </div>
    </button>
  )
}
