import { Route, Routes } from 'react-router'
import { AppLayout } from '@/components/layout/AppLayout'
import { PATHS } from '@/constants/navigation'
import AiProcessingPage from '@/pages/admin/AiProcessingPage'
import CamerasPage from '@/pages/admin/CamerasPage'
import VideoProcessingPage from '@/pages/admin/VideoProcessingPage'
import ModelsPage from '@/pages/admin/ModelsPage'
import UsersPage from '@/pages/admin/UsersPage'
import CaseBrowserPage from '@/pages/cases/CaseBrowserPage'
import LoginPage from '@/pages/LoginPage'
import AuditLogPage from '@/pages/monitor/AuditLogPage'
import DiagnosticsPage from '@/pages/monitor/DiagnosticsPage'
import SystemStatusPage from '@/pages/monitor/SystemStatusPage'
import SearchPage from '@/pages/operator/SearchPage'
import OverviewPage from '@/pages/viewer/OverviewPage'
import { RedirectHome, RequireAuth, RequireRole } from './guards'

export function AppRoutes() {
  return (
    <Routes>
      <Route path={PATHS.login} element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route element={<RequireRole roles={['admin']} />}>
            <Route path={PATHS.users} element={<UsersPage />} />
            <Route path={PATHS.cameras} element={<CamerasPage />} />
            <Route path={PATHS.ai} element={<AiProcessingPage />} />
            <Route path={PATHS.models} element={<ModelsPage />} />
            <Route path={PATHS.videos} element={<VideoProcessingPage />} />
            <Route path={PATHS.status} element={<SystemStatusPage />} />
            <Route path={PATHS.diagnostics} element={<DiagnosticsPage />} />
            <Route path={PATHS.audit} element={<AuditLogPage />} />
          </Route>
          <Route element={<RequireRole roles={['operator']} />}>
            <Route path={PATHS.search} element={<SearchPage />} />
            <Route path={PATHS.cases} element={<CaseBrowserPage mode="operator" />} />
          </Route>
          <Route element={<RequireRole roles={['viewer']} />}>
            <Route path={PATHS.overview} element={<OverviewPage />} />
            <Route path={PATHS.caseFiles} element={<CaseBrowserPage mode="viewer" />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<RedirectHome />} />
    </Routes>
  )
}
