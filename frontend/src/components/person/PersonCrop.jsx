import { ImageBrokenIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { cx } from '@/components/ui/cx'

// Card frame is 3:5. The backend grows the crop around the person with real frame pixels to
// this ratio (tall boxes gain width, wide boxes gain height), so the image fills the card, and
// marks the matched person (outline + dimmed surroundings) since the wider crop can include
// other people.
const CARD_ASPECT = 3 / 5

export function PersonCrop({ result, rank }) {
  const [failedUrl, setFailedUrl] = useState(null)
  // Near frame borders the ratio may not be reachable; then show the whole crop instead of
  // letting object-cover cut the person.
  const [fillsCard, setFillsCard] = useState(true)
  const src = result.cropUrl && `${result.cropUrl}?aspect=${CARD_ASPECT.toFixed(2)}&mark=1`
  const available = result.hasFrame && Boolean(src) && failedUrl !== src
  return (
    <div className="relative aspect-[3/5] overflow-hidden rounded-md bg-[linear-gradient(180deg,var(--color-neutral-800),var(--color-neutral-900))]">
      {available ? (
        <img
          src={src}
          alt={`Người xuất hiện tại ${result.camName} lúc ${result.when}`}
          className={cx('h-full w-full', fillsCard ? 'object-cover' : 'object-contain')}
          onLoad={(e) => {
            const { naturalWidth: w, naturalHeight: h } = e.currentTarget
            setFillsCard(Math.abs(w / h - CARD_ASPECT) / CARD_ASPECT < 0.05)
          }}
          onError={() => setFailedUrl(src)}
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center p-2 text-center text-[11px] text-neutral-400">
          <div className="flex flex-col items-center gap-1">
            <ImageBrokenIcon size={20} />
            <div>Không còn ảnh</div>
          </div>
        </div>
      )}
      {rank != null && (
        <span className="absolute top-1.5 left-1.5 rounded-sm bg-[color-mix(in_srgb,var(--color-bg)_80%,transparent)] px-1.5 py-px text-[11px] font-medium text-accent-200">
          #{rank}
        </span>
      )}
    </div>
  )
}
