import { useContext } from 'react'
import { AppStoreContext, ConfirmContext, ToastContext } from './contexts'

const useRequired = (context, name) => {
  const value = useContext(context)
  if (!value) throw new Error(`${name} must be used within its provider`)
  return value
}

export const useAppStore = () => useRequired(AppStoreContext, 'useAppStore')
export const useToast = () => useRequired(ToastContext, 'useToast')
export const useConfirm = () => useRequired(ConfirmContext, 'useConfirm')
