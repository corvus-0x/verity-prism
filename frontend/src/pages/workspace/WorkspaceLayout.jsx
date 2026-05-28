import { Outlet } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import WorkspaceSidebar from '../../components/layout/WorkspaceSidebar'
import { WorkspaceProvider } from '../../context/WorkspaceContext'

export default function WorkspaceLayout() {
  return (
    <WorkspaceProvider>
      <AppShell>
        <WorkspaceSidebar />
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </AppShell>
    </WorkspaceProvider>
  )
}
