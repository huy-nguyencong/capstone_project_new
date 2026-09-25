import { XIcon } from '@phosphor-icons/react'
import { IconButton } from './Button'
import { cx } from './cx'

export function Panel({ as: Tag = 'div', className, children, ...props }) {
  return (
    <Tag className={cx('panel', className)} {...props}>
      {children}
    </Tag>
  )
}

export function SidePanel({ title, subtitle, onClose, children }) {
  return (
    <aside className="flex flex-col gap-3 rounded-md bg-surface p-4 shadow-md">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-base font-medium">{title}</div>
          {subtitle && <div className="text-xs text-neutral-400">{subtitle}</div>}
        </div>
        <IconButton icon={XIcon} label="Đóng" onClick={onClose} />
      </div>
      {children}
    </aside>
  )
}

export function KeyValueList({ items, className }) {
  return (
    <dl className={cx('grid grid-cols-[auto_1fr] gap-x-3.5 gap-y-2 text-[13px]', className)}>
      {items.map(({ k, v, mono }) => (
        <div key={k} className="contents">
          <dt className="text-neutral-400">{k}</dt>
          <dd className={cx('m-0 break-words', mono && 'font-mono')}>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function MasterDetail({ detail, children }) {
  return (
    <div
      className={cx(
        'grid items-start gap-3.5',
        detail ? 'grid-cols-1 xl:grid-cols-[minmax(0,1fr)_300px]' : 'grid-cols-1',
      )}
    >
      {children}
      {detail}
    </div>
  )
}
