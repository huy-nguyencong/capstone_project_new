import { ImageBrokenIcon } from '@phosphor-icons/react'
import { cx } from '@/components/ui/cx'
import { PersonFigure } from './PersonFigure'

export function SceneFrame({ osd, aspect = '16/9', className, children }) {
  return (
    <div
      className={cx(
        'relative overflow-hidden bg-[repeating-linear-gradient(90deg,transparent_0_79px,color-mix(in_srgb,var(--color-text)_3%,transparent)_79px_80px),linear-gradient(180deg,var(--color-neutral-900),var(--color-bg)_58%,var(--color-neutral-900))]',
        className,
      )}
      style={{ aspectRatio: aspect }}
    >
      {osd && (
        <div className="absolute top-2.5 left-3 font-mono text-[11px] font-medium tracking-[0.04em] text-neutral-300">
          {osd}
        </div>
      )}
      {children}
    </div>
  )
}

export function BoundingBox({ box, label, dashed, className, children }) {
  return (
    <div
      className={cx(
        'absolute rounded-[2px]',
        dashed
          ? 'border border-dashed border-neutral-600'
          : 'border-[1.5px] border-accent shadow-[0_0_20px_color-mix(in_srgb,var(--color-accent)_40%,transparent)]',
        className,
      )}
      style={{ left: `${box.x}%`, top: `${box.y}%`, width: `${box.w}%`, height: `${box.h}%` }}
    >
      {children}
      {label && (
        <div className="absolute bottom-full -left-[1.5px] mb-1 rounded-[3px] bg-accent-800 px-1.5 py-px text-[10px] whitespace-nowrap text-accent-100">
          {label}
        </div>
      )}
    </div>
  )
}

export function ResultScene({ result }) {
  return (
    <SceneFrame osd={result.osd} className="rounded-md">
      {result.hasFrame ? (
        <BoundingBox box={result.bbox} label={`${result.track} · ${result.scoreText}`}>
          <PersonFigure shirt={result.shirt} pants={result.pants} bag={result.bag} layout="scene" />
        </BoundingBox>
      ) : (
        <div className="absolute inset-0 grid place-items-center p-4 text-center text-[13px] text-neutral-300">
          <div className="flex flex-col items-center gap-1">
            <ImageBrokenIcon size={28} />
            <div>
              Không thể dựng ảnh người — frame toàn cảnh hoặc bounding box không còn khả dụng.
            </div>
            <div className="text-xs text-neutral-500">Metadata vẫn được hiển thị bên cạnh.</div>
          </div>
        </div>
      )}
    </SceneFrame>
  )
}
