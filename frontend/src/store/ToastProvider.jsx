import { useCallback, useEffect, useRef, useState } from 'react'
import { TONE } from '@/constants/status'
import { ToastContext } from './contexts'

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)
  const timer = useRef(null)

  const show = useCallback((msg, kind = 'ok') => {
    clearTimeout(timer.current)
    setToast({ msg, kind, key: Date.now() })
    timer.current = setTimeout(() => setToast(null), 4200)
  }, [])

  useEffect(() => () => clearTimeout(timer.current), [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div
          key={toast.key}
          role="status"
          className="fixed right-5 bottom-5 z-[80] flex max-w-[420px] items-start gap-2.5 rounded-md bg-surface px-3.5 py-3 text-[13px] shadow-lg"
        >
          <span
            className="mt-1.5 size-2 flex-none rounded-full"
            style={{ background: TONE[toast.kind] ?? TONE.ok }}
          />
          <span className="text-pretty">{toast.msg}</span>
        </div>
      )}
    </ToastContext.Provider>
  )
}
