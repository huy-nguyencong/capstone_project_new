import { cx } from './cx'

export function Switch({ checked, onChange, disabled, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onChange}
      className={cx(
        'relative h-[22px] w-[38px] rounded-full border p-0 disabled:opacity-45',
        checked
          ? 'border-accent bg-[color-mix(in_srgb,var(--color-accent)_30%,transparent)]'
          : 'border-neutral-600 bg-transparent',
      )}
    >
      <span
        className={cx(
          'absolute top-[3px] size-3.5 rounded-full transition-[left] duration-150',
          checked ? 'left-[19px] bg-accent-200' : 'left-[3px] bg-neutral-500',
        )}
      />
    </button>
  )
}
