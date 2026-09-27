import { Dot } from './StatusDot'
import { cx } from './cx'

export function MetricCard({ label, value, tone, size = 'md', highlight, className }) {
  return (
    <div
      className={cx(
        'rounded-md shadow-sm',
        size === 'lg' ? 'px-4 py-3.5 sm:px-[22px] sm:py-5' : 'px-4 py-3.5',
        highlight
          ? 'bg-[linear-gradient(160deg,color-mix(in_srgb,var(--color-accent)_10%,var(--color-surface)),var(--color-surface)_60%)]'
          : 'bg-surface',
        className,
      )}
    >
      <div className="flex items-center gap-[7px] text-xs text-neutral-300">
        {tone && <Dot tone={tone} />}
        {label}
      </div>
      <div
        className={cx(
          'mt-1.5 leading-[1.1] font-medium',
          size === 'lg' ? 'text-[32px] sm:text-[44px]' : 'text-[28px]',
        )}
      >
        {value}
      </div>
    </div>
  )
}
