import { ImageBrokenIcon } from '@phosphor-icons/react'
import { PersonFigure } from './PersonFigure'

export function PersonCrop({ result, showScore = true, rank }) {
  return (
    <div className="relative aspect-[3/5] overflow-hidden rounded-md bg-[linear-gradient(180deg,var(--color-neutral-800),var(--color-neutral-900))]">
      {result.hasFrame ? (
        <PersonFigure shirt={result.shirt} pants={result.pants} bag={result.bag} />
      ) : (
        <div className="absolute inset-0 grid place-items-center p-2 text-center text-[11px] text-neutral-400">
          <div className="flex flex-col items-center gap-1">
            <ImageBrokenIcon size={20} />
            <div>Không thể dựng ảnh người</div>
          </div>
        </div>
      )}
      {showScore && (
        <span className="absolute top-1.5 left-1.5 rounded-sm bg-[color-mix(in_srgb,var(--color-bg)_80%,transparent)] px-1.5 py-px text-[11px] font-medium text-accent-200">
          {result.scoreText}
        </span>
      )}
      {rank != null && (
        <span className="absolute bottom-1.5 left-1.5 font-mono text-[10px] text-neutral-300">
          #{rank}
        </span>
      )}
    </div>
  )
}
