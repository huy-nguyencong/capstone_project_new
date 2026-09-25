import { cx } from './cx'

export function DataTable({
  columns,
  rows,
  rowKey,
  onRowClick,
  selectedKey,
  emptyText,
  rowClassName,
}) {
  return (
    <div className="panel overflow-x-auto">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={cx(c.align === 'right' && 'text-right')}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row)
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cx(
                  onRowClick && 'cursor-pointer',
                  selectedKey === key && 'is-selected',
                  rowClassName?.(row),
                )}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cx(c.align === 'right' && 'text-right', c.className)}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
      {!rows.length && emptyText && (
        <div className="px-4 py-7 text-[13px] text-neutral-400">{emptyText}</div>
      )}
    </div>
  )
}

export function CellStack({ primary, secondary, mono }) {
  return (
    <div>
      <div className="text-sm">{primary}</div>
      {secondary && (
        <div className={cx('text-neutral-400', mono ? 'font-mono text-[11px]' : 'text-xs')}>
          {secondary}
        </div>
      )}
    </div>
  )
}
