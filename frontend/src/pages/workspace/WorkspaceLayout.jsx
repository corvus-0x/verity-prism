import { Outlet } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import WorkspaceSidebar from '../../components/layout/WorkspaceSidebar'
import { WorkspaceProvider } from '../../context/WorkspaceContext'
import { ToastProvider } from '../../hooks/useToast'

export default function WorkspaceLayout() {
  return (
    <WorkspaceProvider>
      <ToastProvider>
        <AppShell>
          <WorkspaceSidebar />
          <div className="flex-1 overflow-auto p-6">
            <Outlet />
          </div>
        </AppShell>
      </ToastProvider>
    </WorkspaceProvider>
  )
}
