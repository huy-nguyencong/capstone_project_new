import { Dot } from './StatusDot'
import { cx } from './cx'

export function Chip({ active, dot, swatch, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx('chip', active && 'is-on')}
    >
      {dot && <Dot color={dot} size={6} />}
      {swatch && (
        <span
          className="size-2.5 rounded-[3px] shadow-[0_0_0_1px_color-mix(in_srgb,var(--color-text)_20%,transparent)]"
          style={{ background: swatch }}
        />
      )}
      {children}
    </button>
  )
}

export function OptionCard({ active, className, children, ...props }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cx('option-card', active && 'is-on', className)}
      {...props}
    >
      {children}
    </button>
  )
}
