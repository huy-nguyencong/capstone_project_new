import { useEffect, useId } from 'react'
import { createPortal } from 'react-dom'
import { cx } from './cx'

export function Dialog({ title, onClose, actions, width = 440, className, children }) {
  const titleId = useId()

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div className={cx('dialog-backdrop z-50', className)}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="dialog"
        style={{ width: `min(${width}px, 100%)` }}
      >
        <div id={titleId} className="dialog-title">
          {title}
        </div>
        {children}
        {actions && <div className="dialog-actions">{actions}</div>}
      </div>
    </div>,
    document.body,
  )
}
