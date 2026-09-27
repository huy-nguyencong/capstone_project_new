import { CaretDownIcon, CheckIcon } from '@phosphor-icons/react'
import { useEffect, useId, useRef, useState } from 'react'
import { cx } from './cx'

// Select-like popup list whose options can carry an icon or colour swatch (a native <select>
// cannot). Keyboard: Enter/Space/ArrowDown opens; arrows, Home/End move; Enter picks; Esc closes.
export function Dropdown({ id, value, options, placeholder, disabled, onChange, className }) {
  const listId = useId()
  const root = useRef(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const items = [{ value: null, label: placeholder }, ...options]
  const selected = items.find((o) => o.value === value) ?? items[0]

  useEffect(() => {
    if (!open) return undefined
    const close = (e) => root.current && !root.current.contains(e.target) && setOpen(false)
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  const show = () => {
    setActive(Math.max(0, items.indexOf(selected)))
    setOpen(true)
  }
  const pick = (item) => {
    onChange(item.value)
    setOpen(false)
  }
  const onKeyDown = (e) => {
    if (disabled) return
    if (!open) {
      if (['Enter', ' ', 'ArrowDown'].includes(e.key)) {
        e.preventDefault()
        show()
      }
      return
    }
    const moves = {
      ArrowDown: (i) => Math.min(items.length - 1, i + 1),
      ArrowUp: (i) => Math.max(0, i - 1),
      Home: () => 0,
      End: () => items.length - 1,
    }
    if (moves[e.key]) {
      e.preventDefault()
      setActive(moves[e.key])
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      pick(items[active])
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      setOpen(false)
    }
  }

  return (
    <div ref={root} className={cx('relative', className)}>
      <button
        id={id}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={onKeyDown}
        className={cx(
          'input flex w-full items-center gap-2 text-left disabled:opacity-50',
          value == null && 'text-neutral-400',
        )}
      >
        <OptionIcon option={selected} />
        <span className="min-w-0 flex-1 truncate text-left">{selected.label}</span>
        <CaretDownIcon size={12} className="flex-none text-neutral-400" />
      </button>
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full min-w-max overflow-auto rounded-md bg-surface p-1 shadow-lg"
        >
          {items.map((item, index) => (
            <li
              key={String(item.value)}
              role="option"
              aria-selected={item.value === value}
              onPointerEnter={() => setActive(index)}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => pick(item)}
              className={cx(
                'flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-[13px]',
                index === active && 'bg-[color-mix(in_srgb,var(--color-accent)_16%,transparent)]',
                item.value == null && 'text-neutral-400',
              )}
            >
              <OptionIcon option={item} />
              <span className="flex-1">{item.label}</span>
              {item.value === value && <CheckIcon size={12} className="text-accent" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function OptionIcon({ option }) {
  if (option.swatch) {
    return (
      <span
        aria-hidden="true"
        className="size-3 flex-none rounded-[3px] shadow-[0_0_0_1px_color-mix(in_srgb,var(--color-text)_25%,transparent)]"
        style={{ background: option.swatch }}
      />
    )
  }
  const Icon = option.icon
  return Icon ? (
    <Icon size={14} aria-hidden="true" className="flex-none text-accent-300" />
  ) : (
    <span aria-hidden="true" className="size-3.5 flex-none" />
  )
}
