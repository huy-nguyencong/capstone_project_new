import { BrowserRouter } from 'react-router'
import { AppRoutes } from '@/routes/AppRoutes'
import { AppStoreProvider } from '@/store/AppStoreProvider'
import { ConfirmProvider } from '@/store/ConfirmProvider'
import { ToastProvider } from '@/store/ToastProvider'

function App() {
  return (
    <BrowserRouter>
      <AppStoreProvider>
        <ToastProvider>
          <ConfirmProvider>
            <AppRoutes />
          </ConfirmProvider>
        </ToastProvider>
      </AppStoreProvider>
    </BrowserRouter>
  )
}

export default App
