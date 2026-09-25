import { useCallback, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { ConfirmContext } from './contexts'

export function ConfirmProvider({ children }) {
  const [request, setRequest] = useState(null)

  const confirm = useCallback((options) => setRequest(options), [])
  const close = () => setRequest(null)

  const run = () => {
    const action = request.onConfirm
    setRequest(null)
    action?.()
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {request && (
        <Dialog
          title={request.title}
          onClose={close}
          className="z-[60]"
          actions={
            <>
              <Button variant="secondary" onClick={close}>
                Hủy
              </Button>
              <Button variant="primary" onClick={run} autoFocus>
                {request.label}
              </Button>
            </>
          }
        >
          <div className="dialog-body">{request.body}</div>
        </Dialog>
      )}
    </ConfirmContext.Provider>
  )
}
