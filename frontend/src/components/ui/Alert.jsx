import { InfoIcon, SignOutIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { cx } from './cx'

const STYLE = {
  error:
    'border border-[color-mix(in_srgb,var(--color-danger)_55%,transparent)] bg-[color-mix(in_srgb,var(--color-danger)_9%,transparent)]',
  notice: 'bg-accent-900 text-accent-200',
  info: 'bg-bg text-neutral-200',
}

const ICON = {
  error: WarningCircleIcon,
  notice: SignOutIcon,
  info: InfoIcon,
}

export function Alert({ tone = 'error', icon, className, children }) {
  const Icon = icon === undefined ? ICON[tone] : icon
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cx(
        'flex items-start gap-2.5 rounded-md px-3 py-2.5 text-[13px]',
        STYLE[tone],
        className,
      )}
    >
      {Icon && (
        <Icon
          size={16}
          className={cx('mt-0.5 flex-none', tone === 'error' && 'text-danger-soft')}
        />
      )}
      <span className="text-pretty">{children}</span>
    </div>
  )
}
