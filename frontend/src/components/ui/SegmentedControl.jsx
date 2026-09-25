import { useId } from 'react'
import { cx } from './cx'

export function SegmentedControl({ options, value, onChange, stretch = false, className }) {
  const name = useId()
  return (
    <div role="radiogroup" className={cx('seg', stretch && 'flex', className)}>
      {options.map((o) => {
        const Icon = o.icon
        return (
          <label
            key={String(o.value)}
            className={cx('seg-opt', stretch && 'flex-1 justify-center')}
          >
            <input
              type="radio"
              name={name}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            {Icon && <Icon size={15} />}
            {o.label}
          </label>
        )
      })}
    </div>
  )
}
